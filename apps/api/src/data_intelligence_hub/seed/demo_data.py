from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.core.security import hash_password
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
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember

NAMESPACE = uuid.UUID("2df8a496-5ea6-49c3-8aef-9604ac8e6238")
DEFAULT_EMAIL = "owner@example.com"


@dataclass(frozen=True)
class DemoContext:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_ids: dict[str, uuid.UUID]
    source_ids: dict[str, uuid.UUID]
    task_ids: dict[str, uuid.UUID]
    run_ids: dict[str, uuid.UUID]
    raw_record_ids: dict[str, uuid.UUID]
    entity_ids: dict[str, uuid.UUID]
    snapshot_ids: dict[str, uuid.UUID]
    signal_ids: dict[str, uuid.UUID]
    intelligence_ids: dict[str, uuid.UUID]
    alert_rule_ids: dict[str, uuid.UUID]


def _id(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"data-achieve-demo:{key}")


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


async def _merge_all(session: AsyncSession, items: list[Any]) -> None:
    for item in items:
        await session.merge(item)
    await session.flush()


def _demo_password() -> str:
    password = os.getenv("SCRAPY_DEMO_PASSWORD")
    if password is None or len(password) < 8:
        raise RuntimeError("SCRAPY_DEMO_PASSWORD must be set to at least 8 characters")
    return password


def _build_context() -> DemoContext:
    return DemoContext(
        user_id=_id("user-owner"),
        workspace_id=_id("workspace-main"),
        project_ids={
            "ecommerce": _id("project-ecommerce"),
            "content": _id("project-content"),
            "technology": _id("project-technology"),
        },
        source_ids={
            "amazon": _id("source-amazon"),
            "tiktok": _id("source-tiktok"),
            "github": _id("source-github"),
        },
        task_ids={
            "amazon": _id("task-amazon"),
            "tiktok": _id("task-tiktok"),
            "github": _id("task-github"),
        },
        run_ids={
            "amazon-success": _id("run-amazon-success"),
            "tiktok-success": _id("run-tiktok-success"),
            "github-failed": _id("run-github-failed"),
        },
        raw_record_ids={
            "amazon-prev": _id("raw-amazon-prev"),
            "amazon-current": _id("raw-amazon-current"),
            "tiktok-prev": _id("raw-tiktok-prev"),
            "tiktok-current": _id("raw-tiktok-current"),
            "github-prev": _id("raw-github-prev"),
            "github-current": _id("raw-github-current"),
        },
        entity_ids={
            "amazon-product": _id("entity-amazon-product"),
            "tiktok-creator": _id("entity-tiktok-creator"),
            "github-repo": _id("entity-github-repo"),
        },
        snapshot_ids={
            "amazon-prev": _id("snapshot-amazon-prev"),
            "amazon-current": _id("snapshot-amazon-current"),
            "tiktok-prev": _id("snapshot-tiktok-prev"),
            "tiktok-current": _id("snapshot-tiktok-current"),
            "github-prev": _id("snapshot-github-prev"),
            "github-current": _id("snapshot-github-current"),
        },
        signal_ids={
            "amazon-price-drop": _id("signal-amazon-price-drop"),
            "tiktok-views-spike": _id("signal-tiktok-views-spike"),
            "github-stars-surge": _id("signal-github-stars-surge"),
        },
        intelligence_ids={
            "amazon-margin-risk": _id("intel-amazon-margin-risk"),
            "tiktok-demand-window": _id("intel-tiktok-demand-window"),
            "github-open-source-momentum": _id("intel-github-open-source-momentum"),
        },
        alert_rule_ids={
            "price": _id("alert-rule-price"),
            "traffic": _id("alert-rule-traffic"),
        },
    )


async def seed_demo_data() -> None:
    password = _demo_password()
    email = os.getenv("SCRAPY_DEMO_EMAIL", DEFAULT_EMAIL)
    name = os.getenv("SCRAPY_DEMO_NAME", "Data Achieve Owner")
    context = _build_context()
    now = _now()

    async with async_session_factory() as session:
        await _merge_identity(session, context, email, password, name, now)
        await _merge_projects(session, context, now)
        await _merge_collection_layer(session, context, now)
        await _merge_entity_layer(session, context, now)
        await _merge_intelligence_layer(session, context, now)
        await _merge_reports_alerts_notifications(session, context, now)
        await session.commit()

    print(f"Seeded demo workspace for {email}")


async def _merge_identity(
    session: AsyncSession,
    context: DemoContext,
    email: str,
    password: str,
    name: str,
    now: datetime,
) -> None:
    await _merge_all(
        session,
        [
            User(
                id=context.user_id,
                email=email,
                password_hash=hash_password(password),
                name=name,
                status="active",
                created_at=now - timedelta(days=30),
                updated_at=now,
            ),
            Workspace(
                id=context.workspace_id,
                name="Data Achieve Intelligence Hub",
                slug="data-achieve-demo",
                owner_id=context.user_id,
                created_at=now - timedelta(days=30),
                updated_at=now,
            ),
            WorkspaceMember(
                id=_id("workspace-member-owner"),
                workspace_id=context.workspace_id,
                user_id=context.user_id,
                role="owner",
                created_at=now - timedelta(days=30),
                updated_at=now,
            ),
        ],
    )


async def _merge_projects(session: AsyncSession, context: DemoContext, now: datetime) -> None:
    await _merge_all(
        session,
        [
            Project(
                id=context.project_ids["ecommerce"],
                workspace_id=context.workspace_id,
                name="跨境电商机会监控",
                description="跟踪核心商品价格、评论热度、竞品动作与渠道风险。",
                domain="ecommerce",
                status="active",
                owner_id=context.user_id,
                created_at=now - timedelta(days=20),
                updated_at=now,
            ),
            Project(
                id=context.project_ids["content"],
                workspace_id=context.workspace_id,
                name="内容增长信号台",
                description="监控短视频、创作者和内容主题的异常增长窗口。",
                domain="content",
                status="active",
                owner_id=context.user_id,
                created_at=now - timedelta(days=18),
                updated_at=now,
            ),
            Project(
                id=context.project_ids["technology"],
                workspace_id=context.workspace_id,
                name="AI 开源生态雷达",
                description="追踪 GitHub 项目、Release、Star 增速与社区动向。",
                domain="technology",
                status="active",
                owner_id=context.user_id,
                created_at=now - timedelta(days=16),
                updated_at=now,
            ),
        ],
    )


async def _merge_collection_layer(
    session: AsyncSession,
    context: DemoContext,
    now: datetime,
) -> None:
    source_items = [
        Source(
            id=context.source_ids["amazon"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["ecommerce"],
            name="Amazon Best Sellers 采集",
            type="generic_web",
            url="https://www.amazon.com/Best-Sellers/zgbs",
            config={"selector": ".zg-grid-general-faceout", "fields": ["title", "price", "rank"]},
            schedule_cron="*/30 * * * *",
            enabled=True,
            created_at=now - timedelta(days=13),
            updated_at=now,
        ),
        Source(
            id=context.source_ids["tiktok"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["content"],
            name="TikTok Creator Watchlist",
            type="manual_json",
            url=None,
            config={"source": "creator_watchlist", "tracked_tags": ["ai tools", "shopify"]},
            schedule_cron="0 */2 * * *",
            enabled=True,
            created_at=now - timedelta(days=12),
            updated_at=now,
        ),
        Source(
            id=context.source_ids["github"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["technology"],
            name="GitHub AI Agent Topic",
            type="github_topic",
            url="https://github.com/topics/ai-agent",
            config={"topic": "ai-agent", "min_stars": 500},
            schedule_cron="15 */1 * * *",
            enabled=True,
            created_at=now - timedelta(days=11),
            updated_at=now,
        ),
    ]
    await _merge_all(session, source_items)

    task_items = [
        CollectionTask(
            id=context.task_ids["amazon"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["ecommerce"],
            source_id=context.source_ids["amazon"],
            collector_type="generic_web",
            name="Amazon 类目价格与排名采集",
            schedule_cron="*/30 * * * *",
            status="enabled",
            config={"timeout_seconds": 30, "dedupe": "content_hash"},
            success_count=128,
            failure_count=2,
            last_run_at=now - timedelta(minutes=18),
            created_at=now - timedelta(days=13),
            updated_at=now,
        ),
        CollectionTask(
            id=context.task_ids["tiktok"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["content"],
            source_id=context.source_ids["tiktok"],
            collector_type="manual_json",
            name="创作者增长样本导入",
            schedule_cron="0 */2 * * *",
            status="enabled",
            config={"schema": "creator_metric_snapshot"},
            success_count=64,
            failure_count=0,
            last_run_at=now - timedelta(hours=1),
            created_at=now - timedelta(days=12),
            updated_at=now,
        ),
        CollectionTask(
            id=context.task_ids["github"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["technology"],
            source_id=context.source_ids["github"],
            collector_type="github_topic",
            name="GitHub Topic 项目追踪",
            schedule_cron="15 */1 * * *",
            status="enabled",
            config={"include_releases": True},
            success_count=91,
            failure_count=3,
            last_run_at=now - timedelta(minutes=42),
            created_at=now - timedelta(days=11),
            updated_at=now,
        ),
    ]
    await _merge_all(session, task_items)

    run_items = [
        TaskRun(
            id=context.run_ids["amazon-success"],
            task_id=context.task_ids["amazon"],
            workspace_id=context.workspace_id,
            status="success",
            started_at=now - timedelta(minutes=20),
            finished_at=now - timedelta(minutes=18),
            records_count=42,
            entities_count=12,
            error_message=None,
            error_traceback=None,
            logs=[{"step": "collector_finished", "records": 42}],
            created_at=now - timedelta(minutes=18),
        ),
        TaskRun(
            id=context.run_ids["tiktok-success"],
            task_id=context.task_ids["tiktok"],
            workspace_id=context.workspace_id,
            status="success",
            started_at=now - timedelta(hours=1, minutes=6),
            finished_at=now - timedelta(hours=1),
            records_count=18,
            entities_count=6,
            error_message=None,
            error_traceback=None,
            logs=[{"step": "manual_json_imported", "records": 18}],
            created_at=now - timedelta(hours=1),
        ),
        TaskRun(
            id=context.run_ids["github-failed"],
            task_id=context.task_ids["github"],
            workspace_id=context.workspace_id,
            status="failed",
            started_at=now - timedelta(minutes=45),
            finished_at=now - timedelta(minutes=42),
            records_count=0,
            entities_count=0,
            error_message="GitHub rate limit reached, retry scheduled",
            error_traceback=None,
            logs=[{"step": "collector_failed", "reason": "rate_limit"}],
            created_at=now - timedelta(minutes=42),
        ),
    ]
    await _merge_all(session, run_items)

    await _merge_all(
        session,
        [
            _raw_record(
                context,
                "amazon-prev",
                context.project_ids["ecommerce"],
                context.source_ids["amazon"],
                context.run_ids["amazon-success"],
                "https://www.amazon.com/dp/demo-air-filter",
                {"title": "Portable Air Quality Filter", "price": 49.9, "rank": 18, "rating": 4.4},
                now - timedelta(days=2),
            ),
            _raw_record(
                context,
                "amazon-current",
                context.project_ids["ecommerce"],
                context.source_ids["amazon"],
                context.run_ids["amazon-success"],
                "https://www.amazon.com/dp/demo-air-filter",
                {"title": "Portable Air Quality Filter", "price": 39.9, "rank": 6, "rating": 4.6},
                now - timedelta(minutes=19),
            ),
            _raw_record(
                context,
                "tiktok-prev",
                context.project_ids["content"],
                context.source_ids["tiktok"],
                context.run_ids["tiktok-success"],
                "https://www.tiktok.com/@demo_creator",
                {"handle": "@demo_creator", "views_24h": 210000, "engagement_rate": 0.061},
                now - timedelta(days=1),
            ),
            _raw_record(
                context,
                "tiktok-current",
                context.project_ids["content"],
                context.source_ids["tiktok"],
                context.run_ids["tiktok-success"],
                "https://www.tiktok.com/@demo_creator",
                {"handle": "@demo_creator", "views_24h": 690000, "engagement_rate": 0.093},
                now - timedelta(hours=1),
            ),
            _raw_record(
                context,
                "github-prev",
                context.project_ids["technology"],
                context.source_ids["github"],
                context.run_ids["github-failed"],
                "https://github.com/demo/agent-runtime",
                {"repo": "demo/agent-runtime", "stars": 12800, "forks": 820},
                now - timedelta(days=3),
            ),
            _raw_record(
                context,
                "github-current",
                context.project_ids["technology"],
                context.source_ids["github"],
                context.run_ids["github-failed"],
                "https://github.com/demo/agent-runtime",
                {"repo": "demo/agent-runtime", "stars": 15100, "forks": 1010},
                now - timedelta(minutes=45),
            ),
        ],
    )


def _raw_record(
    context: DemoContext,
    key: str,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    task_run_id: uuid.UUID,
    source_url: str,
    content: dict[str, Any],
    collected_at: datetime,
) -> RawRecord:
    return RawRecord(
        id=context.raw_record_ids[key],
        workspace_id=context.workspace_id,
        project_id=project_id,
        source_id=source_id,
        task_run_id=task_run_id,
        record_type="metric_snapshot",
        source_url=source_url,
        content=content,
        content_hash=str(context.raw_record_ids[key]).replace("-", ""),
        screenshot_url=None,
        collected_at=collected_at,
        created_at=collected_at,
    )


async def _merge_entity_layer(
    session: AsyncSession,
    context: DemoContext,
    now: datetime,
) -> None:
    await _merge_all(
        session,
        [
            Entity(
                id=context.entity_ids["amazon-product"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["ecommerce"],
                entity_type="product",
                external_id="amazon:demo-air-filter",
                canonical_url="https://www.amazon.com/dp/demo-air-filter",
                name="Portable Air Quality Filter",
                domain="ecommerce",
                latest_snapshot_id=None,
                first_seen_at=now - timedelta(days=2),
                last_seen_at=now - timedelta(minutes=19),
                created_at=now - timedelta(days=2),
                updated_at=now,
            ),
            Entity(
                id=context.entity_ids["tiktok-creator"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["content"],
                entity_type="creator",
                external_id="tiktok:@demo_creator",
                canonical_url="https://www.tiktok.com/@demo_creator",
                name="@demo_creator",
                domain="content",
                latest_snapshot_id=None,
                first_seen_at=now - timedelta(days=1),
                last_seen_at=now - timedelta(hours=1),
                created_at=now - timedelta(days=1),
                updated_at=now,
            ),
            Entity(
                id=context.entity_ids["github-repo"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["technology"],
                entity_type="repository",
                external_id="github:demo/agent-runtime",
                canonical_url="https://github.com/demo/agent-runtime",
                name="demo/agent-runtime",
                domain="technology",
                latest_snapshot_id=None,
                first_seen_at=now - timedelta(days=3),
                last_seen_at=now - timedelta(minutes=45),
                created_at=now - timedelta(days=3),
                updated_at=now,
            ),
        ],
    )

    snapshot_items = [
        _snapshot(
            context,
            "amazon-prev",
            "amazon-product",
            {"price": 49.9, "rank": 18},
            now - timedelta(days=2),
        ),
        _snapshot(
            context,
            "amazon-current",
            "amazon-product",
            {"price": 39.9, "rank": 6},
            now - timedelta(minutes=19),
        ),
        _snapshot(
            context,
            "tiktok-prev",
            "tiktok-creator",
            {"views_24h": 210000, "engagement_rate": 0.061},
            now - timedelta(days=1),
        ),
        _snapshot(
            context,
            "tiktok-current",
            "tiktok-creator",
            {"views_24h": 690000, "engagement_rate": 0.093},
            now - timedelta(hours=1),
        ),
        _snapshot(
            context,
            "github-prev",
            "github-repo",
            {"stars": 12800, "forks": 820},
            now - timedelta(days=3),
        ),
        _snapshot(
            context,
            "github-current",
            "github-repo",
            {"stars": 15100, "forks": 1010},
            now - timedelta(minutes=45),
        ),
    ]
    await _merge_all(session, snapshot_items)

    latest_map = {
        "amazon-product": context.snapshot_ids["amazon-current"],
        "tiktok-creator": context.snapshot_ids["tiktok-current"],
        "github-repo": context.snapshot_ids["github-current"],
    }
    for entity_key, snapshot_id in latest_map.items():
        entity = await session.get(Entity, context.entity_ids[entity_key])
        if entity is not None:
            entity.latest_snapshot_id = snapshot_id
    await session.flush()

    await _merge_all(
        session,
        [
            Signal(
                id=context.signal_ids["amazon-price-drop"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["ecommerce"],
                entity_id=context.entity_ids["amazon-product"],
                signal_type="price_drop",
                previous_snapshot_id=context.snapshot_ids["amazon-prev"],
                current_snapshot_id=context.snapshot_ids["amazon-current"],
                current_value=39.9,
                previous_value=49.9,
                delta=-10.0,
                delta_ratio=-0.2004,
                confidence=0.91,
                severity="high",
                metadata_json={"metric": "price", "threshold": 0.15, "currency": "USD"},
                detected_at=now - timedelta(minutes=18),
            ),
            Signal(
                id=context.signal_ids["tiktok-views-spike"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["content"],
                entity_id=context.entity_ids["tiktok-creator"],
                signal_type="traffic_spike",
                previous_snapshot_id=context.snapshot_ids["tiktok-prev"],
                current_snapshot_id=context.snapshot_ids["tiktok-current"],
                current_value=690000,
                previous_value=210000,
                delta=480000,
                delta_ratio=2.2857,
                confidence=0.88,
                severity="medium",
                metadata_json={"metric": "views_24h", "threshold": 1.5},
                detected_at=now - timedelta(hours=1),
            ),
            Signal(
                id=context.signal_ids["github-stars-surge"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["technology"],
                entity_id=context.entity_ids["github-repo"],
                signal_type="community_growth",
                previous_snapshot_id=context.snapshot_ids["github-prev"],
                current_snapshot_id=context.snapshot_ids["github-current"],
                current_value=15100,
                previous_value=12800,
                delta=2300,
                delta_ratio=0.1797,
                confidence=0.84,
                severity="medium",
                metadata_json={"metric": "stars", "window": "72h"},
                detected_at=now - timedelta(minutes=44),
            ),
        ],
    )


def _snapshot(
    context: DemoContext,
    snapshot_key: str,
    entity_key: str,
    metrics: dict[str, Any],
    captured_at: datetime,
) -> EntitySnapshot:
    return EntitySnapshot(
        id=context.snapshot_ids[snapshot_key],
        entity_id=context.entity_ids[entity_key],
        raw_record_id=context.raw_record_ids[snapshot_key],
        snapshot_data={"metrics": metrics, "source": "demo_seed"},
        metrics=metrics,
        captured_at=captured_at,
        created_at=captured_at,
    )


async def _merge_intelligence_layer(
    session: AsyncSession,
    context: DemoContext,
    now: datetime,
) -> None:
    await _merge_all(
        session,
        [
            IntelligenceItem(
                id=context.intelligence_ids["amazon-margin-risk"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["ecommerce"],
                title="竞品价格 20% 下探，可能压缩当前商品毛利窗口",
                summary=(
                    "Amazon 目标商品价格从 49.9 降至 39.9，排名同步升至第 6；"
                    "需要评估跟价策略与库存周转。"
                ),
                intelligence_type="risk",
                status="new",
                impact_score=0.88,
                confidence_score=0.91,
                novelty_score=0.76,
                urgency_score=0.92,
                final_score=0.87,
                generated_by="rule",
                domain="ecommerce",
                created_at=now - timedelta(minutes=16),
                updated_at=now,
            ),
            IntelligenceItem(
                id=context.intelligence_ids["tiktok-demand-window"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["content"],
                title="短视频创作者 24h 播放量放大 3.3 倍，出现投放窗口",
                summary=(
                    "目标创作者围绕 AI tools 内容的播放量从 21 万提升到 69 万，"
                    "互动率同步增长至 9.3%。"
                ),
                intelligence_type="opportunity",
                status="following",
                impact_score=0.81,
                confidence_score=0.88,
                novelty_score=0.83,
                urgency_score=0.79,
                final_score=0.83,
                generated_by="rule",
                domain="content",
                created_at=now - timedelta(hours=1),
                updated_at=now,
            ),
            IntelligenceItem(
                id=context.intelligence_ids["github-open-source-momentum"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["technology"],
                title="AI Agent Runtime 开源项目 72h Star 增长 17.9%",
                summary=(
                    "目标仓库 Star 从 12,800 提升到 15,100，社区关注度上升；"
                    "适合进入技术雷达观察清单。"
                ),
                intelligence_type="trend",
                status="reviewed",
                impact_score=0.74,
                confidence_score=0.84,
                novelty_score=0.72,
                urgency_score=0.63,
                final_score=0.74,
                generated_by="rule",
                domain="technology",
                created_at=now - timedelta(minutes=43),
                updated_at=now,
            ),
        ],
    )

    await _merge_all(
        session,
        [
            Evidence(
                id=_id("evidence-amazon-price"),
                intelligence_id=context.intelligence_ids["amazon-margin-risk"],
                signal_id=context.signal_ids["amazon-price-drop"],
                entity_id=context.entity_ids["amazon-product"],
                raw_record_id=context.raw_record_ids["amazon-current"],
                evidence_type="signal",
                title="价格指标从 49.9 降至 39.9",
                url="https://www.amazon.com/dp/demo-air-filter",
                excerpt="Current price: 39.9, rank: 6",
                highlighted_text="price drop -20.0%",
                created_at=now - timedelta(minutes=16),
            ),
            Evidence(
                id=_id("evidence-tiktok-views"),
                intelligence_id=context.intelligence_ids["tiktok-demand-window"],
                signal_id=context.signal_ids["tiktok-views-spike"],
                entity_id=context.entity_ids["tiktok-creator"],
                raw_record_id=context.raw_record_ids["tiktok-current"],
                evidence_type="signal",
                title="播放量 24h 提升至 69 万",
                url="https://www.tiktok.com/@demo_creator",
                excerpt="views_24h: 690000, engagement_rate: 0.093",
                highlighted_text="traffic spike +228.6%",
                created_at=now - timedelta(hours=1),
            ),
            Evidence(
                id=_id("evidence-github-stars"),
                intelligence_id=context.intelligence_ids["github-open-source-momentum"],
                signal_id=context.signal_ids["github-stars-surge"],
                entity_id=context.entity_ids["github-repo"],
                raw_record_id=context.raw_record_ids["github-current"],
                evidence_type="signal",
                title="Star 增长 2,300",
                url="https://github.com/demo/agent-runtime",
                excerpt="stars: 15100, forks: 1010",
                highlighted_text="community growth +17.9%",
                created_at=now - timedelta(minutes=43),
            ),
        ],
    )


async def _merge_reports_alerts_notifications(
    session: AsyncSession,
    context: DemoContext,
    now: datetime,
) -> None:
    report_id = _id("report-daily")
    await _merge_all(
        session,
        [
            Report(
                id=report_id,
                workspace_id=context.workspace_id,
                project_id=None,
                report_type="daily",
                title="Data Achieve 每日情报摘要",
                content=(
                    "今日共识别 3 条高价值情报：电商价格下探、内容流量放大、AI 开源项目增长。"
                    "建议优先处理价格风险，并把内容增长窗口转化为投放实验。"
                ),
                status="generated",
                period_start=now - timedelta(days=1),
                period_end=now,
                created_at=now - timedelta(minutes=8),
            ),
            AlertRule(
                id=context.alert_rule_ids["price"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["ecommerce"],
                name="价格跌幅超过 15%",
                signal_type="price_drop",
                condition={"delta_ratio_lte": -0.15},
                channel="both",
                enabled=True,
                created_at=now - timedelta(days=7),
            ),
            AlertRule(
                id=context.alert_rule_ids["traffic"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["content"],
                name="流量增长超过 150%",
                signal_type="traffic_spike",
                condition={"delta_ratio_gte": 1.5},
                channel="in_app",
                enabled=True,
                created_at=now - timedelta(days=6),
            ),
        ],
    )

    await _merge_all(
        session,
        [
            AlertEvent(
                id=_id("alert-event-price"),
                rule_id=context.alert_rule_ids["price"],
                signal_id=context.signal_ids["amazon-price-drop"],
                status="sent",
                payload={"title": "价格跌幅超过 15%", "delta_ratio": -0.2004},
                triggered_at=now - timedelta(minutes=15),
                sent_at=now - timedelta(minutes=14),
            ),
            AlertEvent(
                id=_id("alert-event-traffic"),
                rule_id=context.alert_rule_ids["traffic"],
                signal_id=context.signal_ids["tiktok-views-spike"],
                status="triggered",
                payload={"title": "流量增长超过 150%", "delta_ratio": 2.2857},
                triggered_at=now - timedelta(hours=1),
                sent_at=None,
            ),
            Notification(
                id=_id("notification-report"),
                user_id=context.user_id,
                title="日报已生成",
                body="Data Achieve 每日情报摘要已准备好，可进入报告页查看。",
                notification_type="report_ready",
                reference_type="report",
                reference_id=report_id,
                is_read=False,
                created_at=now - timedelta(minutes=8),
            ),
            Notification(
                id=_id("notification-alert"),
                user_id=context.user_id,
                title="价格告警已触发",
                body="Portable Air Quality Filter 价格下探 20%，已生成风险情报。",
                notification_type="alert",
                reference_type="alert_event",
                reference_id=_id("alert-event-price"),
                is_read=False,
                created_at=now - timedelta(minutes=14),
            ),
            Notification(
                id=_id("notification-task-failed"),
                user_id=context.user_id,
                title="GitHub 采集任务失败",
                body="GitHub Topic 项目追踪遇到 rate limit，系统已等待下次调度。",
                notification_type="task_failed",
                reference_type="task_run",
                reference_id=context.run_ids["github-failed"],
                is_read=True,
                created_at=now - timedelta(minutes=42),
            ),
        ],
    )


def main() -> None:
    asyncio.run(seed_demo_data())


if __name__ == "__main__":
    main()

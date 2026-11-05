"""freshness_check 纯函数单测(D4 monitor v1)。

evaluate_stale_tasks / build_report_text 不做 I/O;
run()/_notify_workspace_owners 需要 DB,由生产手工验收。
"""

from __future__ import annotations

import uuid

from data_intelligence_hub.maintenance.freshness_check import (
    STALE_GRACE_HOURS,
    StaleTaskItem,
    build_report_text,
    evaluate_stale_tasks,
)
from data_intelligence_hub.models.task import CollectionTask


def _task(
    *,
    name: str = "示例任务",
    config: dict[str, object] | None = None,
    collector_type: str = "provider_api",
) -> CollectionTask:
    return CollectionTask(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        collector_type=collector_type,
        name=name,
        status="active",
        config=config,
    )


def test_stale_when_never_run() -> None:
    task = _task(name="从未运行")
    items = evaluate_stale_tasks([(task, None)])
    assert len(items) == 1
    assert items[0].stale_hours is None
    assert items[0].last_run_at is None


def test_stale_when_beyond_target_plus_grace() -> None:
    # 默认 target 24h + 宽限 48h = 72h;80h 超,60h 未超。
    stale_task = _task(name="超期任务")
    ok_task = _task(name="正常任务")
    items = evaluate_stale_tasks([(stale_task, 80.0), (ok_task, 60.0)])
    assert [i.task_name for i in items] == ["超期任务"]
    assert items[0].stale_hours == round(80.0 - 24 - STALE_GRACE_HOURS, 2)


def test_custom_freshness_target_from_config() -> None:
    task = _task(name="每小时任务", config={"freshness_target_hours": 1})
    items = evaluate_stale_tasks([(task, 60.0)])
    # 60h > 1 + 48 → 超期 11h
    assert len(items) == 1
    assert items[0].freshness_target_hours == 1
    assert items[0].stale_hours == round(60.0 - 1 - STALE_GRACE_HOURS, 2)


def test_within_threshold_not_stale() -> None:
    task = _task()
    assert evaluate_stale_tasks([(task, 24.0 + STALE_GRACE_HOURS)]) == ()


def test_report_text_empty_and_stale() -> None:
    assert build_report_text(()) == "任务新鲜度巡检:全部正常,无超期任务。"
    item = StaleTaskItem(
        task_id=str(uuid.uuid4()),
        task_name="TikTok 日更",
        workspace_id=str(uuid.uuid4()),
        collector_type="provider_api",
        last_run_at=None,
        freshness_target_hours=24,
        stale_hours=None,
    )
    text = build_report_text([item])
    assert "1 个超期任务" in text
    assert "TikTok 日更" in text
    assert "从未运行" in text


def test_report_text_truncates_long_list() -> None:
    items = [
        StaleTaskItem(
            task_id=str(uuid.uuid4()),
            task_name=f"任务{i}",
            workspace_id=str(uuid.uuid4()),
            collector_type="provider_api",
            last_run_at=None,
            freshness_target_hours=24,
            stale_hours=None,
        )
        for i in range(12)
    ]
    text = build_report_text(items)
    assert "另有 2 个" in text

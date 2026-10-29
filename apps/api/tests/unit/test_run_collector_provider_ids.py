"""采集日志里的 provider 标识提取。

SP-10 遗留项之一：``dataset_id`` 没有落库。根因不在提取逻辑，
而在上游——Apify 采集器只把 ``run_id`` 与 ``dataset_id`` 拼进
日志的 message 文本里，从未写成字典键；而提取侧读的是键。

结果是 Apify 这条路径的 ``provider_run_id`` 一直是 ``None``，
``provider_dataset_id`` 更是根本没有列可写。

这些断言固定两件事：
1. 提取只认结构化键，不解析 message 文本（文本是给人看的，会改）。
2. 同一 run 有多条日志时取最近一条（重试时最后一条才对应当前调用）。
"""

from __future__ import annotations

from typing import Any

from data_intelligence_hub.services.run_collector_call import _latest_log_value


def test_returns_none_for_empty_logs() -> None:
    assert _latest_log_value([], "provider_run_id") is None


def test_returns_none_when_key_absent() -> None:
    logs: list[dict[str, Any]] = [
        {"step": "apify_run_created", "message": "run_id=abc123"},
    ]

    # message 里有 run_id，但那不是键。解析文本会在文案改动时静默失效。
    assert _latest_log_value(logs, "provider_run_id") is None


def test_reads_structured_key() -> None:
    logs: list[dict[str, Any]] = [
        {"step": "apify_run_created", "provider_run_id": "run-abc"},
    ]

    assert _latest_log_value(logs, "provider_run_id") == "run-abc"


def test_takes_the_latest_occurrence() -> None:
    """重试会产生多条日志，只有最后一条对应当前调用的 provider 标识。"""

    logs: list[dict[str, Any]] = [
        {"step": "apify_run_created", "provider_dataset_id": "ds-old"},
        {"step": "apify_dataset_fetched", "provider_dataset_id": "ds-new"},
    ]

    assert _latest_log_value(logs, "provider_dataset_id") == "ds-new"


def test_ignores_empty_and_non_string_values() -> None:
    logs: list[dict[str, Any]] = [
        {"step": "x", "provider_dataset_id": ""},
        {"step": "y", "provider_dataset_id": 12345},
        {"step": "z", "provider_dataset_id": None},
    ]

    assert _latest_log_value(logs, "provider_dataset_id") is None


def test_skips_invalid_later_entries_and_falls_back() -> None:
    """最后一条是脏数据时不应把有效值一起丢掉。"""

    logs: list[dict[str, Any]] = [
        {"step": "ok", "provider_run_id": "run-abc"},
        {"step": "bad", "provider_run_id": ""},
    ]

    assert _latest_log_value(logs, "provider_run_id") == "run-abc"

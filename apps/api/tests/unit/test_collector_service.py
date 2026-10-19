"""采集运行状态语义测试。

覆盖四种终态和零产出策略。
"""

from __future__ import annotations

from data_intelligence_hub.collectors.empty_result_policy import EmptyResultPolicy
from data_intelligence_hub.services.collector_service import (
    _collection_failure_reason,
    _resolve_run_status,
    _run_status,
)


class TestRunStatus:
    def test_success(self):
        status = _run_status(
            result_errors=[],
            collected_records=2,
            created_records=2,
        )
        assert status == "success"

    def test_all_deduplicated_records_stay_success(self):
        # 全部去重时原始记录仍大于 0。这是幂等订阅流的正常路径。
        status = _run_status(
            result_errors=[],
            collected_records=1,
            created_records=0,
        )
        assert status == "success"

    def test_zero_records_is_empty(self):
        status = _run_status(
            result_errors=[],
            collected_records=0,
            created_records=0,
        )
        assert status == "empty"

    def test_errors_with_records_is_partial_success(self):
        status = _run_status(
            result_errors=["boom"],
            collected_records=2,
            created_records=2,
        )
        assert status == "partial_success"

    def test_errors_without_records_is_failed(self):
        status = _run_status(
            result_errors=["boom"],
            collected_records=0,
            created_records=0,
        )
        assert status == "failed"


class TestEmptyResultPolicyApplication:
    def test_zero_records_with_permissive_policy_is_empty(self):
        status, errors, log = _resolve_run_status(
            result_errors=[],
            collected_records=0,
            created_records=0,
            policy=EmptyResultPolicy(allow_empty=True),
            collector_type="generic_web",
            endpoint_type=None,
        )
        assert status == "empty"
        assert errors == []
        assert log is not None
        assert log["level"] == "warning"
        assert log["step"] == "collector_empty_result"
        assert log["allow_empty"] is True
        assert log["enforced"] is False

    def test_zero_records_with_strict_policy_is_failed(self):
        status, errors, log = _resolve_run_status(
            result_errors=[],
            collected_records=0,
            created_records=0,
            policy=EmptyResultPolicy(allow_empty=False),
            collector_type="github_repo",
            endpoint_type=None,
        )
        assert status == "failed"
        assert errors == [
            "collector_empty_result: expected >= 1 record(s), got 0 "
            "(collector_type=github_repo, endpoint_type=None)"
        ]
        assert log is not None
        assert log["level"] == "error"
        assert log["enforced"] is True

    def test_strict_policy_uses_min_expected_records(self):
        status, errors, _ = _resolve_run_status(
            result_errors=[],
            collected_records=0,
            created_records=0,
            policy=EmptyResultPolicy(
                allow_empty=False,
                min_expected_records=10,
            ),
            collector_type="tikhub_social",
            endpoint_type="tikhub_tiktok_video_search",
        )
        assert status == "failed"
        assert errors == [
            "collector_empty_result: expected >= 10 record(s), got 0 "
            "(collector_type=tikhub_social, "
            "endpoint_type=tikhub_tiktok_video_search)"
        ]

    def test_errors_with_zero_records_stay_failed(self):
        # 已有错误时零产出仍是失败。宽松策略不追加 empty 错误。
        status, errors, log = _resolve_run_status(
            result_errors=["http_timeout: upstream did not respond"],
            collected_records=0,
            created_records=0,
            policy=EmptyResultPolicy(allow_empty=True),
            collector_type="generic_web",
            endpoint_type=None,
        )
        assert status == "failed"
        assert errors == ["http_timeout: upstream did not respond"]
        assert log is None

    def test_records_present_skips_empty_policy(self):
        status, errors, log = _resolve_run_status(
            result_errors=[],
            collected_records=3,
            created_records=0,
            policy=EmptyResultPolicy(allow_empty=False),
            collector_type="github_topic",
            endpoint_type=None,
        )
        assert status == "success"
        assert errors == []
        assert log is None


class TestFailureReason:
    def test_empty_result_reason(self):
        reason = _collection_failure_reason(
            "collector_empty_result: expected >= 1 record(s), got 0"
        )
        assert reason == "empty_result"

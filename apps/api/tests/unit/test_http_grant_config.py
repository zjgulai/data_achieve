"""受控 HTTP 采集的域名授权配置校验。

启动期校验器只报告问题，不抛异常。
运行时 http_grant 继续使用原有异常类型和消息。
"""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from data_intelligence_hub.collectors import outbound_policy
from data_intelligence_hub.collectors.outbound_policy import (
    GUARDED_HTTP_COLLECTORS,
    CollectionPolicyDenied,
    validate_collection_http_grants,
)
from data_intelligence_hub.core.config import Settings

VALID_EXPIRES_AT = "2099-01-01T00:00:00Z"
VALID_HOST = "www.example.com"


def _grant(
    collector_type: str = "generic_web",
    **overrides: object,
) -> dict[str, object]:
    grant: dict[str, object] = {
        "collector_type": collector_type,
        "hosts": [VALID_HOST],
        "expires_at": VALID_EXPIRES_AT,
    }
    grant.update(overrides)
    return grant


def _issues(grant: dict[str, object]) -> list[str]:
    return validate_collection_http_grants([grant])


def _assert_issue_mentions_field(grant: dict[str, object], field: str) -> str:
    issues = _issues(grant)
    assert issues, "校验器必须报告问题"
    matches = [issue for issue in issues if field in issue]
    assert matches, f"错误说明必须包含字段名 {field}：{issues}"
    return matches[0]


@pytest.mark.parametrize("collector_type", sorted(GUARDED_HTTP_COLLECTORS))
def test_each_guarded_collector_passes_validation(collector_type: str) -> None:
    assert _issues(_grant(collector_type)) == []


def test_all_four_grants_pass_validation() -> None:
    grants = [_grant(name) for name in sorted(GUARDED_HTTP_COLLECTORS)]
    assert validate_collection_http_grants(grants) == []


def test_valid_optional_budget_passes() -> None:
    grant = _grant(max_requests=1, max_domains=1, timeout_seconds=0.5)
    assert _issues(grant) == []


@pytest.mark.parametrize("field", ["collector_type", "hosts", "expires_at"])
def test_missing_required_field_names_the_field(field: str) -> None:
    grant = _grant()
    grant.pop(field)
    issue = _assert_issue_mentions_field(grant, field)
    assert "缺少必填字段" in issue


def test_unknown_collector_type_is_rejected() -> None:
    issue = _assert_issue_mentions_field(_grant("playwright_browser"), "collector_type")
    assert "受控 HTTP 采集器" in issue


def test_duplicate_collector_type_is_rejected() -> None:
    issues = validate_collection_http_grants(
        [_grant("generic_web"), _grant("generic_web")]
    )
    assert len(issues) == 1
    assert "collector_type" in issues[0]
    assert "重复" in issues[0]
    assert "缺少唯一的服务端域名批准配置" in issues[0]


@pytest.mark.parametrize("hosts", [[], [f"h{i}.example.com" for i in range(6)]])
def test_hosts_count_must_be_one_to_five(hosts: list[str]) -> None:
    issue = _assert_issue_mentions_field(_grant(hosts=hosts), "hosts")
    assert "1 到 5" in issue


@pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
def test_ip_host_is_rejected(host: str) -> None:
    issue = _assert_issue_mentions_field(_grant(hosts=[host]), "hosts")
    assert "IP 地址" in issue


@pytest.mark.parametrize("host", ["api.localhost", "printer.local", "x.onion"])
def test_reserved_suffix_host_is_rejected(host: str) -> None:
    issue = _assert_issue_mentions_field(_grant(hosts=[host]), "hosts")
    assert ".localhost / .local / .onion" in issue


def test_non_string_host_is_rejected() -> None:
    issue = _assert_issue_mentions_field(_grant(hosts=[123]), "hosts")
    assert "字符串" in issue


@pytest.mark.parametrize("value", ["not-a-date", 1700000000])
def test_unparseable_expires_at_names_the_field(value: object) -> None:
    issue = _assert_issue_mentions_field(_grant(expires_at=value), "expires_at")
    assert "ISO-8601" in issue


def test_expires_at_without_timezone_names_the_field() -> None:
    issue = _assert_issue_mentions_field(
        _grant(expires_at="2099-01-01T00:00:00"), "expires_at"
    )
    assert "时区" in issue


def test_expired_grant_names_the_field() -> None:
    issue = _assert_issue_mentions_field(
        _grant(expires_at="2020-01-01T00:00:00Z"), "expires_at"
    )
    assert "过期" in issue


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_requests", 0),
        ("max_requests", 51),
        ("max_domains", 0),
        ("max_domains", 6),
        ("timeout_seconds", 0),
        ("timeout_seconds", 61),
    ],
)
def test_optional_budget_out_of_range_names_the_field(
    field: str,
    value: object,
) -> None:
    issue = _assert_issue_mentions_field(_grant(**{field: value}), field)
    assert "必须" in issue


def test_max_domains_smaller_than_hosts_names_the_field() -> None:
    grant = _grant(hosts=["a.example.com", "b.example.com"], max_domains=1)
    issue = _assert_issue_mentions_field(grant, "max_domains")
    assert "hosts" in issue


def test_non_object_item_reports_its_index() -> None:
    issues = validate_collection_http_grants(["generic_web"])
    assert issues == ["collection_http_grants[0]：必须是 JSON 对象"]


def test_non_array_config_names_the_setting() -> None:
    issues = validate_collection_http_grants({"collector_type": "generic_web"})
    assert issues == ["collection_http_grants：必须是 JSON 数组"]


@pytest.mark.parametrize("collector_type", sorted(GUARDED_HTTP_COLLECTORS))
def test_http_grant_returns_grant_for_each_guarded_collector(
    monkeypatch: pytest.MonkeyPatch,
    collector_type: str,
) -> None:
    grants = [_grant(name) for name in sorted(GUARDED_HTTP_COLLECTORS)]
    settings = Settings(_env_file=None, collection_http_grants=grants)
    monkeypatch.setattr(outbound_policy, "get_settings", lambda: settings)

    grant = outbound_policy.http_grant(collector_type)

    assert grant.collector_type == collector_type
    assert grant.hosts == frozenset({VALID_HOST})
    assert grant.max_requests == 50
    assert grant.max_domains == 5
    assert grant.timeout_seconds == 60.0


def test_duplicate_records_fail_runtime_grant_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    grants = [_grant("generic_web"), _grant("generic_web")]
    settings = Settings(_env_file=None, collection_http_grants=grants)
    monkeypatch.setattr(outbound_policy, "get_settings", lambda: settings)

    with pytest.raises(CollectionPolicyDenied, match="缺少唯一的服务端域名批准配置"):
        outbound_policy.http_grant("generic_web")


def test_startup_check_logs_every_issue() -> None:
    from data_intelligence_hub.main import warn_on_invalid_http_grants

    bad = _grant("unknown_collector", hosts=[], expires_at="bad")
    with capture_logs() as logs:
        warn_on_invalid_http_grants([bad])

    assert logs
    entry = logs[-1]
    assert entry["log_level"] == "warning"
    assert entry["issue_count"] == len(entry["issues"])
    assert entry["issue_count"] >= 3


def test_startup_check_stays_quiet_for_valid_grants() -> None:
    from data_intelligence_hub.main import warn_on_invalid_http_grants

    with capture_logs() as logs:
        warn_on_invalid_http_grants([_grant()])

    assert logs == []

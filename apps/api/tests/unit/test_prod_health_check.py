from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from data_intelligence_hub.maintenance.prod_health_check import (
    ALERT_REASON_FAILURE_CHANGED,
    ALERT_REASON_HEALTHY,
    ALERT_REASON_PERSISTENT,
    ALERT_REASON_SUPPRESSED,
    ALERT_REASON_TRANSITION,
    BITABLE_URL,
    DEFAULT_EXPECTED_SCHEMA,
    DEFAULT_STATE_FILE,
    CheckResult,
    HealthReport,
    build_alert_text,
    build_state,
    config_from_env,
    decide_alert,
    evaluate_health_payload,
    evaluate_status_check,
    run_checks,
)

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def _check(
    name: str,
    *,
    ok: bool,
    status_code: int | None = 200,
    detail: str = "",
) -> CheckResult:
    return CheckResult(
        name=name,
        url=f"http://health.test/{name}",
        ok=ok,
        status_code=status_code,
        detail=detail,
        elapsed_ms=12,
    )


def _report(*checks: CheckResult, checked_at: datetime = NOW) -> HealthReport:
    return HealthReport(checked_at=checked_at, checks=tuple(checks))


def _ready_payload() -> dict[str, object]:
    return {
        "database": "connected",
        "schema": "current",
        "schema_revision": DEFAULT_EXPECTED_SCHEMA,
        "schema_head": DEFAULT_EXPECTED_SCHEMA,
    }


def test_evaluate_health_payload_accepts_ready_schema() -> None:
    ok, detail = evaluate_health_payload(
        200,
        _ready_payload(),
        expected_schema=DEFAULT_EXPECTED_SCHEMA,
    )

    assert ok is True
    assert detail == ""


def test_evaluate_health_payload_rejects_wrong_schema_revision() -> None:
    payload = {**_ready_payload(), "schema_revision": "202610200047"}

    ok, detail = evaluate_health_payload(
        200,
        payload,
        expected_schema=DEFAULT_EXPECTED_SCHEMA,
    )

    assert ok is False
    assert "202610200047" in detail
    assert DEFAULT_EXPECTED_SCHEMA in detail


def test_evaluate_health_payload_rejects_database_failure() -> None:
    payload = {**_ready_payload(), "database": "unavailable"}

    ok, detail = evaluate_health_payload(
        200,
        payload,
        expected_schema=DEFAULT_EXPECTED_SCHEMA,
    )

    assert ok is False
    assert "database='unavailable'" in detail


def test_evaluate_health_payload_rejects_unexpected_schema_status() -> None:
    payload = {**_ready_payload(), "schema": "pending"}

    ok, detail = evaluate_health_payload(
        200,
        payload,
        expected_schema=DEFAULT_EXPECTED_SCHEMA,
    )

    assert ok is False
    assert "schema='pending'" in detail


def test_evaluate_health_payload_rejects_non_200_status() -> None:
    ok, detail = evaluate_health_payload(
        503,
        _ready_payload(),
        expected_schema=DEFAULT_EXPECTED_SCHEMA,
    )

    assert ok is False
    assert detail == "HTTP 503"


def test_evaluate_health_payload_rejects_invalid_body_and_network_error() -> None:
    ok, detail = evaluate_health_payload(
        200,
        None,
        expected_schema=DEFAULT_EXPECTED_SCHEMA,
    )
    assert ok is False
    assert "JSON" in detail

    ok, detail = evaluate_health_payload(
        None,
        None,
        expected_schema=DEFAULT_EXPECTED_SCHEMA,
        error="ConnectError: boom",
    )
    assert ok is False
    assert "ConnectError: boom" in detail


def test_evaluate_status_check_accepts_configured_statuses() -> None:
    allowed = frozenset({200, 401})

    result = evaluate_status_check(
        "tools",
        "http://health.test/api/tools",
        401,
        expected_statuses=allowed,
    )
    assert result.ok is True
    assert result.status_code == 401
    assert result.detail == ""

    result = evaluate_status_check(
        "tools",
        "http://health.test/api/tools",
        200,
        expected_statuses=allowed,
    )
    assert result.ok is True


def test_evaluate_status_check_rejects_unexpected_status_and_errors() -> None:
    result = evaluate_status_check(
        "mcp_auth",
        "http://health.test/mcp/",
        200,
        expected_statuses=frozenset({401}),
    )
    assert result.ok is False
    assert result.status_code == 200
    assert "HTTP 200" in result.detail

    result = evaluate_status_check(
        "mcp_auth",
        "http://health.test/mcp/",
        None,
        expected_statuses=frozenset({401}),
        detail="ConnectError: boom",
    )
    assert result.ok is False
    assert result.status_code is None
    assert result.detail == "ConnectError: boom"


def test_decide_alert_alerts_on_transition_to_failed() -> None:
    report = _report(_check("health", ok=False, status_code=503))

    decision = decide_alert(None, report, NOW)

    assert decision.should_alert is True
    assert decision.reason == ALERT_REASON_TRANSITION
    assert decision.failed_since == NOW


def test_decide_alert_suppresses_repeat_within_six_hours() -> None:
    previous = {
        "status": "failed",
        "failed_since": (NOW - timedelta(hours=2)).isoformat(),
        "failed_checks": ["health"],
        "last_alert_at": (NOW - timedelta(hours=1)).isoformat(),
    }
    report = _report(_check("health", ok=False, status_code=503))

    decision = decide_alert(previous, report, NOW)

    assert decision.should_alert is False
    assert decision.reason == ALERT_REASON_SUPPRESSED
    assert decision.failed_since == NOW - timedelta(hours=2)


def test_decide_alert_repeats_after_six_hours() -> None:
    previous = {
        "status": "failed",
        "failed_since": (NOW - timedelta(hours=8)).isoformat(),
        "failed_checks": ["health"],
        "last_alert_at": (NOW - timedelta(hours=6)).isoformat(),
    }
    report = _report(_check("health", ok=False, status_code=503))

    decision = decide_alert(previous, report, NOW)

    assert decision.should_alert is True
    assert decision.reason == ALERT_REASON_PERSISTENT
    assert decision.failed_since == NOW - timedelta(hours=8)


def test_decide_alert_alerts_when_failed_check_set_changes() -> None:
    previous = {
        "status": "failed",
        "failed_since": (NOW - timedelta(hours=2)).isoformat(),
        "failed_checks": ["health"],
        "last_alert_at": (NOW - timedelta(minutes=10)).isoformat(),
    }
    report = _report(
        _check("health", ok=False, status_code=503),
        _check("mcp_auth", ok=False, status_code=200),
    )

    decision = decide_alert(previous, report, NOW)

    assert decision.should_alert is True
    assert decision.reason == ALERT_REASON_FAILURE_CHANGED
    assert decision.failed_since == NOW


def test_decide_alert_alerts_when_failed_state_has_no_alert_timestamp() -> None:
    previous = {
        "status": "failed",
        "failed_since": (NOW - timedelta(hours=2)).isoformat(),
        "failed_checks": ["health"],
        "last_alert_at": None,
    }
    report = _report(_check("health", ok=False, status_code=503))

    decision = decide_alert(previous, report, NOW)

    assert decision.should_alert is True
    assert decision.reason == ALERT_REASON_TRANSITION


def test_decide_alert_is_silent_after_recovery() -> None:
    previous = {
        "status": "failed",
        "failed_since": (NOW - timedelta(hours=2)).isoformat(),
        "failed_checks": ["health"],
        "last_alert_at": (NOW - timedelta(hours=1)).isoformat(),
    }
    report = _report(_check("health", ok=True))

    decision = decide_alert(previous, report, NOW)

    assert decision.should_alert is False
    assert decision.reason == ALERT_REASON_HEALTHY
    assert decision.failed_since is None


def test_build_state_records_alert_time_and_clears_on_recovery() -> None:
    failed_report = _report(_check("health", ok=False, status_code=503))
    decision = decide_alert(None, failed_report, NOW)

    failed_state = build_state(None, failed_report, decision, NOW, alert_sent=True)
    assert failed_state == {
        "status": "failed",
        "failed_since": NOW.isoformat(),
        "failed_checks": ["health"],
        "last_alert_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
    }

    healthy_report = _report(_check("health", ok=True))
    healthy_decision = decide_alert(failed_state, healthy_report, NOW + timedelta(minutes=10))
    healthy_state = build_state(
        failed_state,
        healthy_report,
        healthy_decision,
        NOW + timedelta(minutes=10),
        alert_sent=False,
    )
    assert healthy_state == {
        "status": "healthy",
        "failed_since": None,
        "failed_checks": [],
        "last_alert_at": None,
        "updated_at": (NOW + timedelta(minutes=10)).isoformat(),
    }


def test_build_state_keeps_last_alert_when_send_fails() -> None:
    previous = {
        "status": "failed",
        "failed_since": (NOW - timedelta(hours=2)).isoformat(),
        "failed_checks": ["health"],
        "last_alert_at": (NOW - timedelta(hours=1)).isoformat(),
    }
    report = _report(_check("health", ok=False, status_code=503))
    decision = decide_alert(previous, report, NOW)

    state = build_state(previous, report, decision, NOW, alert_sent=False)

    assert state["last_alert_at"] == previous["last_alert_at"]
    assert state["failed_since"] == previous["failed_since"]


def test_build_alert_text_lists_failed_checks_status_and_bitable_link() -> None:
    report = _report(
        _check("health", ok=False, status_code=503, detail="database='unavailable'"),
        _check("mcp_auth", ok=False, status_code=200),
        _check("tools", ok=True, status_code=401),
    )

    text = build_alert_text(report, reason=ALERT_REASON_TRANSITION, base_url="http://127.0.0.1:8000")

    assert "[生产 A 健康告警] 2 项检查失败" in text
    assert NOW.isoformat() in text
    assert "http://127.0.0.1:8000" in text
    assert "- health: HTTP 503 database='unavailable'" in text
    assert "- mcp_auth: HTTP 200" in text
    assert "- tools" not in text
    assert BITABLE_URL in text


def test_config_from_env_defaults_and_overrides() -> None:
    defaults = config_from_env({})
    assert defaults.base_url == "http://127.0.0.1:8000"
    assert defaults.expected_schema == DEFAULT_EXPECTED_SCHEMA
    assert str(defaults.state_file) == DEFAULT_STATE_FILE
    assert defaults.alert_open_ids == ("ou_b49d21f41d8b2f119e466d29782d29ff",)
    assert defaults.alerts_disabled is False

    overrides = config_from_env(
        {
            "SCRAPY_HEALTH_BASE_URL": "https://scrapy.example.com/",
            "SCRAPY_HEALTH_EXPECTED_SCHEMA": " 202610200099 ",
            "SCRAPY_HEALTH_STATE_FILE": "/var/lib/scrapy/health.json",
            "HEALTH_ALERT_OPEN_IDS": "ou_first, ou_second ,",
            "HEALTH_ALERTS_DISABLED": "true",
            "LARK_SHUSUO_APP_ID": "cli_test",
            "LARK_SHUSUO_APP_SECRET": "secret_test",
        }
    )
    assert overrides.base_url == "https://scrapy.example.com"
    assert overrides.expected_schema == "202610200099"
    assert str(overrides.state_file) == "/var/lib/scrapy/health.json"
    assert overrides.alert_open_ids == ("ou_first", "ou_second")
    assert overrides.alerts_disabled is True
    assert overrides.lark_app_id == "cli_test"
    assert overrides.lark_app_secret == "secret_test"


def test_run_checks_queries_expected_endpoints_without_network() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/api/health":
            return httpx.Response(200, json=_ready_payload())
        if request.url.path == "/api/tools":
            return httpx.Response(401)
        if request.url.path == "/mcp/":
            return httpx.Response(401)
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = run_checks(
            client,
            base_url="http://health.test",
            expected_schema=DEFAULT_EXPECTED_SCHEMA,
            now=NOW,
        )

    assert report.ok is True
    assert report.checked_at == NOW
    assert [check.name for check in report.checks] == [
        "health",
        "collectors_docs",
        "platform_packages",
        "tools",
        "mcp_auth",
    ]
    assert seen == [
        "/api/health",
        "/api/collectors/docs",
        "/api/platform-packages",
        "/api/tools",
        "/mcp/",
    ]


def test_run_checks_reports_failed_checks_with_status_codes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/health":
            return httpx.Response(200, json={**_ready_payload(), "database": "timeout"})
        if request.url.path == "/api/tools":
            return httpx.Response(500)
        if request.url.path == "/mcp/":
            return httpx.Response(200)
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = run_checks(
            client,
            base_url="http://health.test",
            expected_schema=DEFAULT_EXPECTED_SCHEMA,
            now=NOW,
        )

    assert report.ok is False
    assert report.failure_signature == ("health", "mcp_auth", "tools")
    failed = {check.name: check for check in report.failed_checks}
    assert failed["health"].status_code == 200
    assert "database='timeout'" in failed["health"].detail
    assert failed["tools"].status_code == 500
    assert failed["mcp_auth"].status_code == 200

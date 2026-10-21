"""Production A health check with Feishu alerts.

Run inside the API container:

    python -m data_intelligence_hub.maintenance.prod_health_check

The command checks public endpoints of Production A, prints one compact JSON
report, and exits 0 when healthy or 1 when unhealthy. On a failure transition,
or when the same failure persists for 6 hours, it sends a Feishu text message
to ``HEALTH_ALERT_OPEN_IDS``.

The pure functions in this module (``evaluate_*``, ``decide_alert``,
``build_state``, ``build_alert_text``) do no I/O and are covered by unit tests.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_EXPECTED_SCHEMA = "202610200048"
DEFAULT_STATE_FILE = "/tmp/scrapy_health_state.json"
DEFAULT_ALERT_OPEN_IDS: tuple[str, ...] = ("ou_b49d21f41d8b2f119e466d29782d29ff",)
BITABLE_URL = (
    "https://momcozy-in.feishu.cn/base/XXz5bHAwCa7qv5sTzrCci3jPnxd"
    "?table=tbli8kAkAqrndUvJ"
)
ALERT_REPEAT_AFTER = timedelta(hours=6)
REQUEST_TIMEOUT_SECONDS = 10.0
LARK_API_BASE = "https://open.feishu.cn/open-apis"

ALERT_REASON_TRANSITION = "transition"
ALERT_REASON_FAILURE_CHANGED = "failure_changed"
ALERT_REASON_PERSISTENT = "persistent"
ALERT_REASON_SUPPRESSED = "suppressed"
ALERT_REASON_HEALTHY = "healthy"

REASON_LABELS = {
    ALERT_REASON_TRANSITION: "首次失败",
    ALERT_REASON_FAILURE_CHANGED: "失败项变化",
    ALERT_REASON_PERSISTENT: "同一故障持续 6 小时",
}

# name, path, accepted HTTP statuses
STATUS_CHECKS: tuple[tuple[str, str, frozenset[int]], ...] = (
    ("collectors_docs", "/api/collectors/docs", frozenset({200})),
    ("platform_packages", "/api/platform-packages", frozenset({200})),
    ("tools", "/api/tools", frozenset({200, 401})),
    ("mcp_auth", "/mcp/", frozenset({401})),
)


@dataclass(frozen=True)
class HealthConfig:
    base_url: str
    expected_schema: str
    state_file: Path
    alert_open_ids: tuple[str, ...]
    lark_app_id: str
    lark_app_secret: str
    alerts_disabled: bool


@dataclass(frozen=True)
class CheckResult:
    name: str
    url: str
    ok: bool
    status_code: int | None
    detail: str = ""
    elapsed_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "ok": self.ok,
            "status_code": self.status_code,
            "detail": self.detail,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass(frozen=True)
class HealthReport:
    checked_at: datetime
    checks: tuple[CheckResult, ...]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    @property
    def failed_checks(self) -> tuple[CheckResult, ...]:
        return tuple(check for check in self.checks if not check.ok)

    @property
    def failure_signature(self) -> tuple[str, ...]:
        return tuple(sorted(check.name for check in self.failed_checks))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "ok" if self.ok else "failed",
            "checked_at": self.checked_at.isoformat(),
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class AlertDecision:
    should_alert: bool
    reason: str
    failed_since: datetime | None


def config_from_env(env: Mapping[str, str] | None = None) -> HealthConfig:
    values = os.environ if env is None else env
    base_url = (values.get("SCRAPY_HEALTH_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")
    if not base_url:
        base_url = DEFAULT_BASE_URL
    expected_schema = (
        values.get("SCRAPY_HEALTH_EXPECTED_SCHEMA") or DEFAULT_EXPECTED_SCHEMA
    ).strip()
    state_file_value = (values.get("SCRAPY_HEALTH_STATE_FILE") or DEFAULT_STATE_FILE).strip()
    raw_alert_ids = values.get("HEALTH_ALERT_OPEN_IDS")
    if raw_alert_ids is None or not raw_alert_ids.strip():
        alert_open_ids = DEFAULT_ALERT_OPEN_IDS
    else:
        alert_open_ids = tuple(
            open_id.strip() for open_id in raw_alert_ids.split(",") if open_id.strip()
        )
    disabled_value = (values.get("HEALTH_ALERTS_DISABLED") or "").strip().lower()
    return HealthConfig(
        base_url=base_url,
        expected_schema=expected_schema or DEFAULT_EXPECTED_SCHEMA,
        state_file=Path(state_file_value or DEFAULT_STATE_FILE),
        alert_open_ids=alert_open_ids,
        lark_app_id=(values.get("LARK_SHUSUO_APP_ID") or "").strip(),
        lark_app_secret=(values.get("LARK_SHUSUO_APP_SECRET") or "").strip(),
        alerts_disabled=disabled_value in {"1", "true", "yes", "on"},
    )


def evaluate_health_payload(
    status_code: int | None,
    payload: Any,
    *,
    expected_schema: str,
    error: str = "",
) -> tuple[bool, str]:
    """Evaluate the /api/health response body. Returns (ok, detail)."""
    if error:
        return False, error
    if status_code != 200:
        return False, f"HTTP {status_code}"
    if not isinstance(payload, Mapping):
        return False, "response is not a JSON object"
    database = payload.get("database")
    if database != "connected":
        return False, f"database={database!r}"
    revision = payload.get("schema_revision")
    if revision != expected_schema:
        return False, f"schema_revision={revision!r}, expected {expected_schema}"
    schema_status = payload.get("schema", "current")
    if schema_status != "current":
        return False, f"schema={schema_status!r}"
    return True, ""


def evaluate_status_check(
    name: str,
    url: str,
    status_code: int | None,
    *,
    expected_statuses: frozenset[int],
    detail: str = "",
    elapsed_ms: int | None = None,
) -> CheckResult:
    if status_code is None:
        return CheckResult(
            name=name,
            url=url,
            ok=False,
            status_code=None,
            detail=detail or "no response",
            elapsed_ms=elapsed_ms,
        )
    ok = status_code in expected_statuses
    return CheckResult(
        name=name,
        url=url,
        ok=ok,
        status_code=status_code,
        detail="" if ok else (detail or f"HTTP {status_code}"),
        elapsed_ms=elapsed_ms,
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _previous_signature(previous_state: Mapping[str, Any] | None) -> tuple[str, ...]:
    if previous_state is None:
        return ()
    raw = previous_state.get("failed_checks")
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(sorted(str(item) for item in raw))


def decide_alert(
    previous_state: Mapping[str, Any] | None,
    report: HealthReport,
    now: datetime,
    *,
    repeat_after: timedelta = ALERT_REPEAT_AFTER,
) -> AlertDecision:
    """Decide whether this run must send an alert.

    Rules:
    - healthy: never alert, reset the failure episode;
    - transition to failed or a changed failure set: alert;
    - same failure: alert again after ``repeat_after``.
    """
    if report.ok:
        return AlertDecision(False, ALERT_REASON_HEALTHY, None)

    previous_status = ""
    failed_since = None
    last_alert_at = None
    if previous_state is not None:
        previous_status = str(previous_state.get("status", ""))
        failed_since = _parse_timestamp(previous_state.get("failed_since"))
        last_alert_at = _parse_timestamp(previous_state.get("last_alert_at"))

    if previous_status != "failed":
        return AlertDecision(True, ALERT_REASON_TRANSITION, now)
    if _previous_signature(previous_state) != report.failure_signature:
        return AlertDecision(True, ALERT_REASON_FAILURE_CHANGED, now)
    if last_alert_at is None:
        return AlertDecision(True, ALERT_REASON_TRANSITION, failed_since or now)
    if now - last_alert_at >= repeat_after:
        return AlertDecision(True, ALERT_REASON_PERSISTENT, failed_since or now)
    return AlertDecision(False, ALERT_REASON_SUPPRESSED, failed_since or now)


def build_state(
    previous_state: Mapping[str, Any] | None,
    report: HealthReport,
    decision: AlertDecision,
    now: datetime,
    *,
    alert_sent: bool,
) -> dict[str, Any]:
    """Build the state file payload for the next run."""
    updated_at = now.isoformat()
    if report.ok:
        return {
            "status": "healthy",
            "failed_since": None,
            "failed_checks": [],
            "last_alert_at": None,
            "updated_at": updated_at,
        }

    previous_last_alert = None
    if previous_state is not None:
        previous_last_alert = previous_state.get("last_alert_at")
    if not isinstance(previous_last_alert, str):
        previous_last_alert = None
    failed_since = decision.failed_since or now
    return {
        "status": "failed",
        "failed_since": failed_since.isoformat(),
        "failed_checks": list(report.failure_signature),
        "last_alert_at": updated_at if alert_sent else previous_last_alert,
        "updated_at": updated_at,
    }


def build_alert_text(report: HealthReport, *, reason: str, base_url: str) -> str:
    lines = [
        f"[生产 A 健康告警] {len(report.failed_checks)} 项检查失败",
        f"时间: {report.checked_at.isoformat()}",
        f"地址: {base_url}",
        f"触发: {REASON_LABELS.get(reason, reason)}",
        "失败项:",
    ]
    for check in report.failed_checks:
        status = check.status_code if check.status_code is not None else "-"
        suffix = f" {check.detail}" if check.detail else ""
        lines.append(f"- {check.name}: HTTP {status}{suffix}")
    lines.append(f"多维表格: {BITABLE_URL}")
    return "\n".join(lines)


def load_state(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def save_state(path: Path, state: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def _get_json(
    client: httpx.Client,
    url: str,
) -> tuple[int | None, Any, str, int]:
    started = time.perf_counter()
    try:
        response = client.get(url)
    except Exception as exc:  # noqa: BLE001 - one failed check must not stop the run
        return None, None, f"{type(exc).__name__}: {exc}", _elapsed_ms(started)
    elapsed_ms = _elapsed_ms(started)
    try:
        payload = response.json()
    except ValueError:
        payload = None
    return response.status_code, payload, "", elapsed_ms


def _get_status(client: httpx.Client, url: str) -> tuple[int | None, str, int]:
    started = time.perf_counter()
    try:
        response = client.get(url)
    except Exception as exc:  # noqa: BLE001 - one failed check must not stop the run
        return None, f"{type(exc).__name__}: {exc}", _elapsed_ms(started)
    return response.status_code, "", _elapsed_ms(started)


def run_checks(
    client: httpx.Client,
    *,
    base_url: str = DEFAULT_BASE_URL,
    expected_schema: str = DEFAULT_EXPECTED_SCHEMA,
    now: datetime | None = None,
) -> HealthReport:
    base = base_url.rstrip("/")
    checked_at = now or datetime.now(UTC)

    health_url = f"{base}/api/health"
    status_code, payload, error, elapsed_ms = _get_json(client, health_url)
    health_ok, health_detail = evaluate_health_payload(
        status_code,
        payload,
        expected_schema=expected_schema,
        error=error,
    )
    checks = [
        CheckResult(
            name="health",
            url=health_url,
            ok=health_ok,
            status_code=status_code,
            detail=health_detail,
            elapsed_ms=elapsed_ms,
        )
    ]
    for name, path, expected in STATUS_CHECKS:
        url = f"{base}{path}"
        status_code, error, elapsed_ms = _get_status(client, url)
        checks.append(
            evaluate_status_check(
                name,
                url,
                status_code,
                expected_statuses=expected,
                detail=error,
                elapsed_ms=elapsed_ms,
            )
        )
    return HealthReport(checked_at=checked_at, checks=tuple(checks))


def fetch_tenant_token(client: httpx.Client, *, app_id: str, app_secret: str) -> str:
    if not app_id or not app_secret:
        raise RuntimeError("LARK_SHUSUO_APP_ID / LARK_SHUSUO_APP_SECRET are not configured")
    response = client.post(
        f"{LARK_API_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, Mapping) or data.get("code") != 0:
        raise RuntimeError(f"Feishu tenant token error: {data!r}")
    token = data.get("tenant_access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Feishu tenant token missing")
    return token


def send_feishu_text(
    client: httpx.Client,
    *,
    open_ids: Sequence[str],
    text: str,
    app_id: str,
    app_secret: str,
) -> list[str]:
    if not open_ids:
        raise RuntimeError("HEALTH_ALERT_OPEN_IDS is empty")
    token = fetch_tenant_token(client, app_id=app_id, app_secret=app_secret)
    content = json.dumps({"text": text}, ensure_ascii=False)
    message_ids: list[str] = []
    for open_id in open_ids:
        response = client.post(
            f"{LARK_API_BASE}/im/v1/messages",
            params={"receive_id_type": "open_id"},
            headers={"Authorization": f"Bearer {token}"},
            json={"receive_id": open_id, "msg_type": "text", "content": content},
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, Mapping) or data.get("code") != 0:
            raise RuntimeError(f"Feishu send error for {open_id}: {data!r}")
        payload = data.get("data")
        message_id = payload.get("message_id") if isinstance(payload, Mapping) else None
        message_ids.append(str(message_id or ""))
    return message_ids


def main(env: Mapping[str, str] | None = None) -> int:
    config = config_from_env(env)
    now = datetime.now(UTC)
    previous_state = load_state(config.state_file)

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        report = run_checks(
            client,
            base_url=config.base_url,
            expected_schema=config.expected_schema,
            now=now,
        )
        decision = decide_alert(previous_state, report, now)
        alert_sent = False
        alert_error = ""
        if decision.should_alert and not config.alerts_disabled:
            text = build_alert_text(report, reason=decision.reason, base_url=config.base_url)
            try:
                send_feishu_text(
                    client,
                    open_ids=config.alert_open_ids,
                    text=text,
                    app_id=config.lark_app_id,
                    app_secret=config.lark_app_secret,
                )
                alert_sent = True
            except Exception as exc:  # noqa: BLE001 - report the send error in JSON
                alert_error = f"{type(exc).__name__}: {exc}"

    state = build_state(previous_state, report, decision, now, alert_sent=alert_sent)
    state_error = ""
    try:
        save_state(config.state_file, state)
    except OSError as exc:
        state_error = f"{type(exc).__name__}: {exc}"

    payload = report.to_dict()
    payload["base_url"] = config.base_url
    payload["expected_schema"] = config.expected_schema
    payload["state_file"] = str(config.state_file)
    payload["alert"] = {
        "should_alert": decision.should_alert,
        "reason": decision.reason,
        "sent": alert_sent,
        "disabled": config.alerts_disabled,
    }
    if alert_error:
        payload["alert"]["error"] = alert_error
    if state_error:
        payload["state_error"] = state_error
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())

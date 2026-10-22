"""Exa Agent 采集器。

异步研究任务：提交 POST /agent/runs，轮询 GET /agent/runs/{id}，
完成后把 output.text / output.structured / grounding 落成一条记录。

同步执行在采集器内完成轮询；MCP 的异步 start/check 由 runs 队列承担。
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select, update

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_http_error_message,
    collector_log,
    require_text,
)
from data_intelligence_hub.collectors.exa_collector import _exa_client, _get_api_key
from data_intelligence_hub.collectors.outbound_policy import assert_collector_allowed
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models.task import TaskRun

_VALID_EFFORTS = frozenset(
    {"minimal", "low", "medium", "high", "xhigh", "auto", "ultra"}
)
_TERMINAL_STATUSES = frozenset(
    {"completed", "succeeded", "failed", "canceled", "cancelled", "error"}
)


async def _load_provider_run_id(
    local_task_run_id: str | None,
    local_run_id: str | None,
) -> str | None:
    task_run_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    try:
        task_run_id = uuid.UUID(local_task_run_id) if local_task_run_id else None
        run_id = uuid.UUID(local_run_id) if local_run_id else None
    except ValueError:
        return None
    async with async_session_factory() as session:
        if task_run_id is not None:
            value = await session.scalar(
                select(TaskRun.provider_run_id).where(TaskRun.id == task_run_id)
            )
            if value:
                return value
        if run_id is not None:
            return await session.scalar(
                select(TaskRun.provider_run_id)
                .where(
                    TaskRun.run_id == run_id,
                    TaskRun.provider_run_id.is_not(None),
                )
                .order_by(TaskRun.created_at.desc())
                .limit(1)
            )
    return None


async def _save_provider_run_id(local_task_run_id: str | None, provider_run_id: str) -> None:
    if not local_task_run_id:
        return
    try:
        task_run_id = uuid.UUID(local_task_run_id)
    except ValueError:
        return
    async with async_session_factory() as session:
        await session.execute(
            update(TaskRun)
            .where(TaskRun.id == task_run_id)
            .values(provider_run_id=provider_run_id)
        )
        await session.commit()


async def cancel_agent_run(provider_run_id: str) -> bool:
    """Best-effort cancel of one remote Exa Agent run."""
    try:
        async with _exa_client(_get_api_key()) as client:
            response = await client.post(f"/agent/runs/{provider_run_id}/cancel")
        return response.status_code in {200, 202, 204, 409}
    except (CollectorError, httpx.HTTPError):
        return False


class ExaAgentCollector(BaseCollector):
    collector_type = "exa_agent"
    allow_empty = False

    def validate_config(self) -> dict[str, Any]:
        assert_collector_allowed(self.collector_type)
        query = require_text(self.config, "query")
        effort = self.config.get("effort", "medium")
        if effort not in _VALID_EFFORTS:
            raise CollectorError(f"effort must be one of {sorted(_VALID_EFFORTS)}")
        output_schema = self.config.get("output_schema")
        if output_schema is not None and not isinstance(output_schema, dict):
            raise CollectorError("output_schema must be a dict (JSON Schema)")
        max_cost = self.config.get("max_cost_dollars", 5)
        if not isinstance(max_cost, (int, float)) or not (1 <= max_cost <= 100):
            raise CollectorError("max_cost_dollars must be 1-100")
        timeout_seconds = self.config.get("timeout_seconds", 600)
        if not isinstance(timeout_seconds, int) or not (30 <= timeout_seconds <= 1800):
            raise CollectorError("timeout_seconds must be 30-1800")
        poll_interval = self.config.get("poll_interval_seconds", 2)
        if not isinstance(poll_interval, (int, float)) or not (1 <= poll_interval <= 30):
            raise CollectorError("poll_interval_seconds must be 1-30")
        return {
            "query": query,
            "effort": effort,
            "output_schema": output_schema,
            "system_prompt": self.config.get("system_prompt"),
            "max_cost_dollars": max_cost,
            "timeout_seconds": timeout_seconds,
            "poll_interval_seconds": poll_interval,
            "local_task_run_id": self.config.get("local_task_run_id"),
            "local_run_id": self.config.get("local_run_id"),
        }

    async def test(self) -> CollectorTestResult:
        """只读探测：列出最近的 agent runs，不创建新任务、不产生费用。"""
        assert_collector_allowed(self.collector_type)
        try:
            api_key = _get_api_key()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed",
                message=str(exc),
                logs=[collector_log("exa_agent_test_failed", str(exc), level="error")],
            )
        try:
            async with _exa_client(api_key) as client:
                response = await client.get("/agent/runs", params={"limit": 1})
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("exa_agent_test_failed", msg, level="error")],
            )
        if response.status_code != 200:
            return CollectorTestResult(
                status="failed",
                message=f"Exa /agent/runs HTTP {response.status_code}",
                logs=[collector_log("exa_agent_test_failed", response.text[:200])],
            )
        return CollectorTestResult(
            status="ok",
            message="Exa /agent/runs reachable",
            logs=[collector_log("exa_agent_test_ok", "ok")],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        try:
            config = self.validate_config()
            api_key = _get_api_key()
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("exa_agent_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        payload: dict[str, Any] = {
            "query": config["query"],
            "effort": config["effort"],
        }
        # Exa 只允许 auto / ultra 设置 budget。固定 effort 按次计费；
        # 给它们发送 budget 会返回 400。
        if config["effort"] in {"auto", "ultra"}:
            payload["budget"] = {"maxCostDollars": config["max_cost_dollars"]}
        if config.get("system_prompt"):
            payload["systemPrompt"] = config["system_prompt"]
        if config.get("output_schema"):
            payload["outputSchema"] = config["output_schema"]

        collected_at = datetime.now(UTC)
        try:
            async with _exa_client(api_key) as client:
                run_id = await _load_provider_run_id(
                    config.get("local_task_run_id"), config.get("local_run_id")
                )
                if not run_id:
                    created = await client.post("/agent/runs", json=payload)
                    if created.status_code not in {200, 201}:
                        msg = (
                            f"Exa /agent/runs HTTP {created.status_code}: "
                            f"{created.text[:300]}"
                        )
                        errors.append(msg)
                        logs.append(collector_log("exa_agent_error", msg, level="error"))
                        return CollectionResult(raw_records=[], logs=logs, errors=errors)
                    run_id = str(created.json().get("id") or "")
                    if not run_id:
                        errors.append("Exa /agent/runs returned no id")
                        return CollectionResult(raw_records=[], logs=logs, errors=errors)
                    # 独立事务立即持久化。租约丢失/进程重启后只继续轮询，
                    # 不会再次 POST 产生第二笔付费运行。
                    await _save_provider_run_id(config.get("local_task_run_id"), run_id)
                    logs.append(collector_log("exa_agent_submitted", f"run_id={run_id}"))
                else:
                    logs.append(collector_log("exa_agent_resumed", f"run_id={run_id}"))

                deadline = asyncio.get_event_loop().time() + config["timeout_seconds"]
                status = "running"
                data: dict[str, Any] = {}
                while asyncio.get_event_loop().time() < deadline:
                    await asyncio.sleep(config["poll_interval_seconds"])
                    polled = await client.get(f"/agent/runs/{run_id}")
                    if polled.status_code == 429 or polled.status_code >= 500:
                        retry_after = polled.headers.get("retry-after")
                        if retry_after and retry_after.isdigit():
                            await asyncio.sleep(min(int(retry_after), 30))
                        continue
                    if polled.status_code != 200:
                        msg = (
                            f"Exa /agent/runs/{run_id} HTTP {polled.status_code}: "
                            f"{polled.text[:300]}"
                        )
                        errors.append(msg)
                        logs.append(collector_log("exa_agent_error", msg, level="error"))
                        return CollectionResult(raw_records=[], logs=logs, errors=errors)
                    data = polled.json()
                    status = str(data.get("status") or "")
                    if status in _TERMINAL_STATUSES:
                        break
                else:
                    # 本地预算到期时必须通知 Exa 取消，避免远端继续消耗额度。
                    try:
                        await client.post(f"/agent/runs/{run_id}/cancel")
                    except httpx.HTTPError:
                        logs.append(
                            collector_log(
                                "exa_agent_cancel_failed",
                                f"run_id={run_id}",
                                level="warning",
                            )
                        )
                    msg = f"agent run {run_id} timed out after {config['timeout_seconds']}s"
                    errors.append(msg)
                    logs.append(collector_log("exa_agent_timeout", msg, level="error"))
                    return CollectionResult(raw_records=[], logs=logs, errors=errors)
        except asyncio.CancelledError:
            # 外层执行预算或 worker 关停会取消本协程。尽力撤销 Exa run，
            # 再原样抛出，让执行层保持正确的取消语义。
            if "run_id" in locals() and run_id:
                try:
                    async with _exa_client(api_key) as cancel_client:
                        await cancel_client.post(f"/agent/runs/{run_id}/cancel")
                except httpx.HTTPError:
                    pass
            raise
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("exa_agent_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        output = data.get("output") if isinstance(data.get("output"), dict) else {}
        stop_reason = data.get("stopReason") or data.get("stop_reason")
        content = {
            "query": config["query"],
            "agent_run_id": run_id,
            "status": status,
            "stop_reason": stop_reason,
            "text": output.get("text"),
            "structured": output.get("structured"),
            "grounding": output.get("grounding"),
            "usage": data.get("usage"),
            "cost": data.get("costDollars"),
        }
        records: list[CollectorRawRecord] = []
        truncated = stop_reason not in (None, "completed", "success")
        if status in {"completed", "succeeded"}:
            records.append(
                CollectorRawRecord(
                    record_type="agent_research",
                    source_url=None,
                    content=content,
                    collected_at=collected_at,
                )
            )
            if truncated:
                errors.append(f"agent run stopped early: {stop_reason}")
        else:
            errors.append(f"agent run ended with status={status}")
        logs.append(
            collector_log(
                "exa_agent_collected",
                f"run_id={run_id} status={status} records={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)
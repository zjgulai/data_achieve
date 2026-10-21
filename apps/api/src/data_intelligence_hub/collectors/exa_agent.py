"""Exa Agent 采集器。

异步研究任务：提交 POST /agent/runs，轮询 GET /agent/runs/{id}，
完成后把 output.text / output.structured / grounding 落成一条记录。

同步执行在采集器内完成轮询；MCP 的异步 start/check 由 runs 队列承担。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

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

_VALID_EFFORTS = frozenset(
    {"minimal", "low", "medium", "high", "xhigh", "auto", "ultra"}
)
_TERMINAL_STATUSES = frozenset(
    {"completed", "succeeded", "failed", "canceled", "cancelled", "error"}
)


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
            "budget": {"maxCostDollars": config["max_cost_dollars"]},
        }
        if config.get("system_prompt"):
            payload["systemPrompt"] = config["system_prompt"]
        if config.get("output_schema"):
            payload["outputSchema"] = config["output_schema"]

        collected_at = datetime.now(UTC)
        try:
            async with _exa_client(api_key) as client:
                created = await client.post("/agent/runs", json=payload)
                if created.status_code not in {200, 201}:
                    msg = f"Exa /agent/runs HTTP {created.status_code}: {created.text[:300]}"
                    errors.append(msg)
                    logs.append(collector_log("exa_agent_error", msg, level="error"))
                    return CollectionResult(raw_records=[], logs=logs, errors=errors)
                run_id = str(created.json().get("id") or "")
                if not run_id:
                    errors.append("Exa /agent/runs returned no id")
                    return CollectionResult(raw_records=[], logs=logs, errors=errors)

                deadline = asyncio.get_event_loop().time() + config["timeout_seconds"]
                status = "running"
                data: dict[str, Any] = {}
                while asyncio.get_event_loop().time() < deadline:
                    await asyncio.sleep(config["poll_interval_seconds"])
                    polled = await client.get(f"/agent/runs/{run_id}")
                    if polled.status_code != 200:
                        continue
                    data = polled.json()
                    status = str(data.get("status") or "")
                    if status in _TERMINAL_STATUSES:
                        break
                else:
                    msg = f"agent run {run_id} timed out after {config['timeout_seconds']}s"
                    errors.append(msg)
                    logs.append(collector_log("exa_agent_timeout", msg, level="error"))
                    return CollectionResult(raw_records=[], logs=logs, errors=errors)
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("exa_agent_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        output = data.get("output") if isinstance(data.get("output"), dict) else {}
        content = {
            "query": config["query"],
            "agent_run_id": run_id,
            "status": status,
            "text": output.get("text"),
            "structured": output.get("structured"),
            "grounding": output.get("grounding"),
            "usage": data.get("usage"),
            "cost": data.get("costDollars"),
        }
        records: list[CollectorRawRecord] = []
        if status in {"completed", "succeeded"}:
            records.append(
                CollectorRawRecord(
                    record_type="agent_research",
                    source_url=None,
                    content=content,
                    collected_at=collected_at,
                )
            )
        else:
            errors.append(f"agent run ended with status={status}")
        logs.append(
            collector_log(
                "exa_agent_collected",
                f"run_id={run_id} status={status} records={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)
from __future__ import annotations

from typing import Any

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    JsonContent,
    collector_log,
    require_text,
)


class ManualJsonCollector(BaseCollector):
    collector_type = "manual_json"

    def validate_config(self) -> dict[str, Any]:
        entity_type = require_text(self.config, "entity_type")
        json_data = self.config.get("json_data")
        if not isinstance(json_data, dict | list):
            raise CollectorError("json_data must be a JSON object or array")
        return {"entity_type": entity_type, "json_data": json_data}

    async def test(self) -> CollectorTestResult:
        self.validate_config()
        return CollectorTestResult(
            status="ok",
            message="Manual JSON payload is valid.",
            logs=[collector_log("collector_tested", "Manual JSON payload validated.")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        json_data = config["json_data"]
        if not isinstance(json_data, dict | list):
            raise CollectorError("json_data must be a JSON object or array")
        content: JsonContent = {
            "provider": "manual_json",
            "kind": "manual_payload",
            "entity_type": config["entity_type"],
            "payload": json_data,
        }
        return CollectionResult(
            raw_records=[
                CollectorRawRecord(
                    record_type="manual_json",
                    source_url=None,
                    content=content,
                )
            ],
            logs=[collector_log("manual_json_collected", "Collected manual JSON payload.")],
            errors=[],
        )

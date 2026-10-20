"""REST surface for the eight TikTok content tools."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from data_intelligence_hub.services.tiktok_tools import TOOL_SPECS, run_tiktok_tool

router = APIRouter(tags=["tiktok-tools"])


class TikTokToolRequest(BaseModel):
    project_id: uuid.UUID
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("")
async def list_tiktok_tools() -> list[dict[str, Any]]:
    return [
        {"tool_id": tool_id, **spec} for tool_id, spec in TOOL_SPECS.items()
    ]


@router.post("/{tool_id}")
async def run_tiktok_tool_route(
    tool_id: str,
    body: TikTokToolRequest,
) -> dict[str, Any]:
    if tool_id not in TOOL_SPECS:
        raise HTTPException(
            status_code=404,
            detail=f"unknown_tiktok_tool: {tool_id}",
        )
    result = await run_tiktok_tool(tool_id, body.project_id, body.params)
    return result.as_dict()

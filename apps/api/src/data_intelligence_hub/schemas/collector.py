from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class CollectorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    name: str
    description: str
    config_schema: dict[str, Any]
    enabled: bool

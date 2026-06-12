from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from data_intelligence_hub.models.notification import Notification


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    body: str
    notification_type: str
    reference_type: str
    reference_id: uuid.UUID
    is_read: bool
    created_at: datetime

    @classmethod
    def from_model(cls, notification: Notification) -> NotificationResponse:
        return cls.model_validate(notification)


class NotificationReadAllResponse(BaseModel):
    updated_count: int

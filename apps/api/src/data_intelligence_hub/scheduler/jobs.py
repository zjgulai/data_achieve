from __future__ import annotations

import uuid


def collection_job_id(task_id: uuid.UUID) -> str:
    return f"collect_{task_id}"

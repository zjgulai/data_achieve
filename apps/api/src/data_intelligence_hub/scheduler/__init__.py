from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data_intelligence_hub.scheduler.service import CollectionScheduler, SchedulerTickResult

__all__ = ["CollectionScheduler", "SchedulerTickResult"]


def __getattr__(name: str) -> object:
    if name in __all__:
        from data_intelligence_hub.scheduler.service import (
            CollectionScheduler,
            SchedulerTickResult,
        )

        return {
            "CollectionScheduler": CollectionScheduler,
            "SchedulerTickResult": SchedulerTickResult,
        }[name]
    raise AttributeError(name)

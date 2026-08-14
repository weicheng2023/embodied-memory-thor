"""Bounded recent-transition memory with deterministic eviction."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class TransitionRecord:
    """One observation and the transition that produced it."""

    step: int
    observation_id: str
    observation: dict[str, Any]
    action: dict[str, Any]
    success: bool
    error: str


class ShortTermMemory:
    """Keep exactly the most recent ``capacity`` transition records."""

    def __init__(self, capacity: int = 2) -> None:
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity
        self._records: deque[TransitionRecord] = deque(maxlen=capacity)

    def add(
        self,
        *,
        step: int,
        observation: Mapping[str, Any],
        action: Mapping[str, Any],
        success: bool,
        error: str = "",
        observation_id: str | None = None,
    ) -> None:
        """Append a defensive copy and evict the oldest record at K+1."""

        self._records.append(
            TransitionRecord(
                step=int(step),
                observation_id=observation_id or f"observation:{step}",
                observation=deepcopy(dict(observation)),
                action=deepcopy(dict(action)),
                success=bool(success),
                error=str(error or ""),
            )
        )

    def records(self) -> list[dict[str, Any]]:
        """Return JSON-safe defensive copies ordered oldest to newest."""

        return deepcopy([asdict(record) for record in self._records])

    def summarize_recent_context(self) -> dict[str, Any]:
        """Return the bounded context used by later structured planners."""

        return {"capacity": self.capacity, "size": len(self._records), "records": self.records()}

    def find_latest_object(self, object_type: str) -> dict[str, Any] | None:
        """Find the newest visible occurrence of an object type in the window."""

        expected = object_type.casefold()
        for record in reversed(self._records):
            raw_objects = record.observation.get("objects", [])
            if not isinstance(raw_objects, list):
                continue
            for obj in raw_objects:
                if not isinstance(obj, Mapping):
                    continue
                if not bool(obj.get("visible", False)):
                    continue
                if str(obj.get("objectType", "")).casefold() == expected:
                    result = deepcopy(dict(obj))
                    result["provenance"] = {
                        "observation_id": record.observation_id,
                        "observation_step": record.step,
                        "memory_kind": "short_term",
                    }
                    return result
        return None

    def snapshot(self) -> dict[str, Any]:
        """Alias the stable summary for episode logging."""

        return self.summarize_recent_context()

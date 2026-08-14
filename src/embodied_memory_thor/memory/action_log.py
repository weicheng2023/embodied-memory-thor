"""Structured action history for debugging failures and repetition."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class ActionRecord:
    """One planner action and normalized execution result."""

    step: int
    action: dict[str, Any]
    target_object: str | None
    success: bool
    error: str
    timestamp: str
    latency_seconds: float


class ActionLog:
    """Append-only structured log with failure and repetition queries."""

    def __init__(self) -> None:
        self._records: list[ActionRecord] = []

    def add(
        self,
        *,
        step: int,
        action: Mapping[str, Any],
        success: bool,
        error: str = "",
        latency_seconds: float = 0.0,
        timestamp: str | None = None,
    ) -> None:
        """Record one action without retaining environment state."""

        normalized = deepcopy(dict(action))
        self._records.append(
            ActionRecord(
                step=int(step),
                action=normalized,
                target_object=str(normalized.get("objectId")) if normalized.get("objectId") else None,
                success=bool(success),
                error=str(error or ""),
                timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
                latency_seconds=max(0.0, float(latency_seconds)),
            )
        )

    def recent_failures(self, limit: int = 5) -> list[dict[str, Any]]:
        """Return the newest failed actions without mutating the log."""

        if limit < 0:
            raise ValueError("limit cannot be negative")
        failures = [record for record in self._records if not record.success]
        return deepcopy([asdict(record) for record in failures[-limit:]]) if limit else []

    def repetition_count(self, action: Mapping[str, Any]) -> int:
        """Count exact prior normalized occurrences of an action."""

        normalized = dict(action)
        return sum(record.action == normalized for record in self._records)

    def snapshot(self) -> list[dict[str, Any]]:
        """Return a JSON-safe defensive copy of all records."""

        return deepcopy([asdict(record) for record in self._records])

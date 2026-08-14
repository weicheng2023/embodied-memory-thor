"""Planner-safe convergence guards for persistent-memory navigation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


MEMORY_NAVIGATION_POLICY_VERSION = "phase5-memory-navigation-v2"
MEMORY_NAVIGATION_ROTATION_STEP_DEGREES = 90.0
MEMORY_NAVIGATION_NONPROGRESS_ACTION_BUDGET = 3
MEMORY_NAVIGATION_PROGRESS_EPSILON_METERS = 0.05


def quantize_yaw_to_action_grid(
    yaw_degrees: float,
    *,
    step_degrees: float = MEMORY_NAVIGATION_ROTATION_STEP_DEGREES,
) -> float:
    """Map a continuous bearing to the nearest executable rotation heading."""

    yaw = float(yaw_degrees)
    step = float(step_degrees)
    if not math.isfinite(yaw) or not math.isfinite(step) or step <= 0.0:
        raise ValueError("yaw and rotation step must be finite; step must be positive")
    steps_per_turn = 360.0 / step
    if abs(steps_per_turn - round(steps_per_turn)) > 1e-9:
        raise ValueError("rotation step must divide 360 degrees")
    # Explicit half-up rounding avoids Python's alternating tie-to-even behavior.
    index = math.floor((yaw % 360.0) / step + 0.5)
    return (index * step) % 360.0


def _agent_xz(observation: Mapping[str, Any]) -> tuple[float, float] | None:
    agent = observation.get("agent", {})
    position = agent.get("position", {}) if isinstance(agent, Mapping) else {}
    if not isinstance(position, Mapping):
        return None
    try:
        x = float(position["x"])
        z = float(position["z"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(z):
        return None
    return x, z


@dataclass
class MemoryNavigationGuard:
    """Bound consecutive memory-guided actions that make no positional progress."""

    nonprogress_action_budget: int = MEMORY_NAVIGATION_NONPROGRESS_ACTION_BUDGET
    progress_epsilon_meters: float = MEMORY_NAVIGATION_PROGRESS_EPSILON_METERS
    suppressed_record_ids: set[str] = field(default_factory=set)
    active_record_ids: tuple[str, ...] = ()
    nonprogress_streak: int = 0
    escape_count: int = 0
    recovery_count: int = 0
    suppressed_retrieval_count: int = 0

    def __post_init__(self) -> None:
        if self.nonprogress_action_budget < 1:
            raise ValueError("memory-navigation nonprogress budget must be positive")
        if self.progress_epsilon_meters <= 0:
            raise ValueError("memory-navigation progress epsilon must be positive")

    def filter_retrieved(
        self, records: Sequence[Mapping[str, Any]]
    ) -> tuple[dict[str, Any], ...]:
        available: list[dict[str, Any]] = []
        for record in records:
            record_id = str(record.get("record_id", ""))
            if record_id and record_id in self.suppressed_record_ids:
                self.suppressed_retrieval_count += 1
                continue
            available.append(dict(record))
        return tuple(available)

    def record_result(
        self,
        *,
        memory_guided: bool,
        record_ids: Sequence[str],
        observation_before: Mapping[str, Any],
        observation_after: Mapping[str, Any],
    ) -> tuple[str, ...]:
        if not memory_guided:
            self.active_record_ids = ()
            self.nonprogress_streak = 0
            return ()
        cited = tuple(sorted({str(item) for item in record_ids if str(item)}))
        if not cited:
            return ()
        if cited != self.active_record_ids:
            self.active_record_ids = cited
            self.nonprogress_streak = 0
        before = _agent_xz(observation_before)
        after = _agent_xz(observation_after)
        progressed = bool(
            before is not None
            and after is not None
            and math.hypot(after[0] - before[0], after[1] - before[1])
            >= self.progress_epsilon_meters
        )
        if progressed:
            self.nonprogress_streak = 0
            return ()
        self.nonprogress_streak += 1
        if self.nonprogress_streak < self.nonprogress_action_budget:
            return ()
        newly_suppressed = tuple(
            record_id
            for record_id in cited
            if record_id not in self.suppressed_record_ids
        )
        self.suppressed_record_ids.update(newly_suppressed)
        if newly_suppressed:
            self.escape_count += 1
        self.active_record_ids = ()
        self.nonprogress_streak = 0
        return newly_suppressed

    def refresh_visible_records(self, record_ids: Sequence[str]) -> tuple[str, ...]:
        recovered = tuple(
            sorted(
                record_id
                for record_id in {str(item) for item in record_ids if str(item)}
                if record_id in self.suppressed_record_ids
            )
        )
        if recovered:
            self.suppressed_record_ids.difference_update(recovered)
            self.recovery_count += len(recovered)
        return recovered

    def snapshot(self, *, include_record_ids: bool = False) -> dict[str, Any]:
        snapshot = {
            "policy": MEMORY_NAVIGATION_POLICY_VERSION,
            "rotation_step_degrees": MEMORY_NAVIGATION_ROTATION_STEP_DEGREES,
            "nonprogress_action_budget": self.nonprogress_action_budget,
            "progress_epsilon_meters": self.progress_epsilon_meters,
            "escape_count": self.escape_count,
            "recovery_count": self.recovery_count,
            "suppressed_retrieval_count": self.suppressed_retrieval_count,
            "suppressed_record_count": len(self.suppressed_record_ids),
            "nonprogress_streak": self.nonprogress_streak,
        }
        if include_record_ids:
            snapshot["suppressed_record_ids"] = sorted(self.suppressed_record_ids)
        return snapshot

"""Interchangeable history providers for one shared partial-observation planner."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol

from embodied_memory_thor.memory.object_memory import ObjectMemory
from embodied_memory_thor.memory.short_term_memory import ShortTermMemory


@dataclass(frozen=True)
class MemoryHint:
    """One observation-derived target-location hint."""

    object_id: str
    object_type: str
    region: str
    observation_step: int
    source_observation_id: str
    memory_kind: str

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""

        return asdict(self)


class MemoryProvider(Protocol):
    """Minimal history interface consumed by the shared planner and runner."""

    kind: str

    def observe(
        self,
        *,
        step: int,
        observation: Mapping[str, Any],
        action: Mapping[str, Any],
        success: bool,
        error: str,
        observation_id: str,
    ) -> list[str]: ...

    def hint(self, object_type: str) -> MemoryHint | None: ...

    def mark_expected_region_miss(
        self, hint: MemoryHint, observation: Mapping[str, Any], *, step: int
    ) -> bool: ...

    def snapshot(self) -> dict[str, Any]: ...


class NoMemoryProvider:
    """Fair baseline provider that retains no historical observation data."""

    kind = "none"

    def observe(self, **_: Any) -> list[str]:
        return []

    def hint(self, object_type: str) -> None:
        del object_type
        return None

    def mark_expected_region_miss(self, *args: Any, **kwargs: Any) -> bool:
        del args, kwargs
        return False

    def snapshot(self) -> dict[str, Any]:
        return {"kind": self.kind, "records": {}}


class ShortTermMemoryProvider:
    """Expose only objects remaining in the frozen recent window."""

    kind = "short_term"

    def __init__(self, capacity: int = 2) -> None:
        self.memory = ShortTermMemory(capacity=capacity)

    def observe(self, **kwargs: Any) -> list[str]:
        self.memory.add(**kwargs)
        return []

    def hint(self, object_type: str) -> MemoryHint | None:
        obj = self.memory.find_latest_object(object_type)
        if obj is None:
            return None
        region = str(obj.get("region", ""))
        provenance = obj.get("provenance", {})
        if not region:
            return None
        return MemoryHint(
            object_id=str(obj.get("objectId", "")),
            object_type=str(obj.get("objectType", object_type)),
            region=region,
            observation_step=int(provenance.get("observation_step", -1)),
            source_observation_id=str(provenance.get("observation_id", "")),
            memory_kind=self.kind,
        )

    def mark_expected_region_miss(self, *args: Any, **kwargs: Any) -> bool:
        del args, kwargs
        return False

    def snapshot(self) -> dict[str, Any]:
        return {"kind": self.kind, "short_term": self.memory.snapshot()}


class ObjectMemoryProvider:
    """Expose persistent, non-stale last-seen records."""

    kind = "object"

    def __init__(self) -> None:
        self.memory = ObjectMemory()

    def observe(self, **kwargs: Any) -> list[str]:
        relevant = {key: kwargs[key] for key in ("step", "observation", "observation_id")}
        return self.memory.update(**relevant)

    def hint(self, object_type: str) -> MemoryHint | None:
        records = self.memory.retrieve(object_type, include_stale=False)
        if not records:
            return None
        record = records[0]
        if not record.last_seen_region:
            return None
        return MemoryHint(
            object_id=record.object_id,
            object_type=record.object_type,
            region=record.last_seen_region,
            observation_step=record.last_seen_step,
            source_observation_id=record.source_observation_id,
            memory_kind=self.kind,
        )

    def mark_expected_region_miss(
        self, hint: MemoryHint, observation: Mapping[str, Any], *, step: int
    ) -> bool:
        return self.memory.mark_expected_region_miss(
            hint.object_id, observation, step=step
        )

    def snapshot(self) -> dict[str, Any]:
        return {"kind": self.kind, "objects": deepcopy(self.memory.snapshot())}


def build_memory_provider(variant: str, *, short_term_capacity: int = 2) -> MemoryProvider:
    """Construct one frozen experimental provider by public variant name."""

    if variant == "no_memory":
        return NoMemoryProvider()
    if variant == "short_memory":
        return ShortTermMemoryProvider(capacity=short_term_capacity)
    if variant == "object_memory":
        return ObjectMemoryProvider()
    raise ValueError(f"unknown memory variant: {variant}")

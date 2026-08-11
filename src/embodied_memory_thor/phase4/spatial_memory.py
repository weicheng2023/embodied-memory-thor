"""Visible-observation-derived spatial memory for real AI2-THOR episodes."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol

from embodied_memory_thor.utils.serialization import to_jsonable


@dataclass
class ThorObjectMemoryRecord:
    """Latest visible object state plus the viewpoint from which it was seen."""

    record_id: str
    object_id: str
    object_type: str
    object_position: dict[str, Any] | None
    last_seen_agent_position: dict[str, Any] | None
    last_seen_agent_rotation: dict[str, Any] | None
    last_seen_camera_horizon: float | None
    last_seen_step: int
    source_observation_id: str
    observed_visible: bool = True
    status: str = "fresh"
    suspected_stale_step: int | None = None

    def snapshot(self) -> dict[str, Any]:
        return to_jsonable(asdict(self))


class ThorMemoryProvider(Protocol):
    """History interface consumed by the Phase 4 runner."""

    kind: str

    def observe(
        self,
        observation: Mapping[str, Any],
        *,
        step: int,
        observation_id: str,
    ) -> list[str]: ...

    def retrieve(self, object_type: str) -> list[dict[str, Any]]: ...

    def snapshot(self) -> dict[str, Any]: ...


class NoThorMemory:
    """Retain no historical observations while preserving the runner contract."""

    kind = "none"

    def observe(self, observation: Mapping[str, Any], **_: Any) -> list[str]:
        del observation
        return []

    def retrieve(self, object_type: str) -> list[dict[str, Any]]:
        del object_type
        return []

    def snapshot(self) -> dict[str, Any]:
        return {"kind": self.kind, "records": {}}


class ThorObjectMemory:
    """Persist only objects present in a planner-safe visible observation."""

    kind = "object"

    def __init__(self) -> None:
        self._records: dict[str, ThorObjectMemoryRecord] = {}

    def observe(
        self,
        observation: Mapping[str, Any],
        *,
        step: int,
        observation_id: str,
    ) -> list[str]:
        records = _records_from_visible_observation(
            observation,
            step=step,
            observation_id=observation_id,
        )
        self._records.update(records)
        return list(records)

    def retrieve(self, object_type: str) -> list[dict[str, Any]]:
        expected = object_type.casefold()
        records = [
            record
            for record in self._records.values()
            if record.object_type.casefold() == expected
            and record.status != "suspected_stale"
        ]
        records.sort(key=lambda item: (-item.last_seen_step, item.object_id))
        return [deepcopy(record.snapshot()) for record in records]

    def mark_suspected_stale(self, record_id: str, *, step: int) -> bool:
        record = self._records.get(record_id)
        if record is None or record.status == "suspected_stale":
            return False
        record.status = "suspected_stale"
        record.suspected_stale_step = int(step)
        return True

    def snapshot(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "records": {
                record_id: deepcopy(record.snapshot())
                for record_id, record in sorted(self._records.items())
            },
        }


class ThorShortMemory:
    """Retain visible records from exactly the last K safe observations."""

    kind = "short"

    def __init__(self, *, k: int = 2) -> None:
        if k <= 0:
            raise ValueError("short-memory K must be positive")
        self.k = int(k)
        self._observations: deque[
            tuple[str, int, dict[str, ThorObjectMemoryRecord]]
        ] = deque(maxlen=self.k)

    def observe(
        self,
        observation: Mapping[str, Any],
        *,
        step: int,
        observation_id: str,
    ) -> list[str]:
        records = _records_from_visible_observation(
            observation,
            step=step,
            observation_id=observation_id,
        )
        self._observations.append((str(observation_id), int(step), records))
        return sorted(records)

    def retrieve(self, object_type: str) -> list[dict[str, Any]]:
        expected = object_type.casefold()
        newest_by_object: dict[str, ThorObjectMemoryRecord] = {}
        for _, _, records in reversed(self._observations):
            for record in records.values():
                if (
                    record.object_type.casefold() == expected
                    and record.object_id not in newest_by_object
                ):
                    newest_by_object[record.object_id] = record
        ordered = sorted(
            newest_by_object.values(),
            key=lambda item: (-item.last_seen_step, item.object_id),
        )
        return [deepcopy(record.snapshot()) for record in ordered]

    def snapshot(self) -> dict[str, Any]:
        records: dict[str, dict[str, Any]] = {}
        for _, _, observation_records in self._observations:
            for record_id, record in observation_records.items():
                records[record_id] = deepcopy(record.snapshot())
        return {
            "kind": self.kind,
            "k": self.k,
            "observation_ids": [item[0] for item in self._observations],
            "records": dict(sorted(records.items())),
        }


def _records_from_visible_observation(
    observation: Mapping[str, Any],
    *,
    step: int,
    observation_id: str,
) -> dict[str, ThorObjectMemoryRecord]:
    """Build provenance-complete records without consulting global metadata."""

    agent = observation.get("agent", {})
    if not isinstance(agent, Mapping):
        agent = {}
    raw_objects = observation.get("objects", [])
    if not isinstance(raw_objects, list):
        return {}

    records: dict[str, ThorObjectMemoryRecord] = {}
    for raw in raw_objects:
        if not isinstance(raw, Mapping) or raw.get("visible") is not True:
            continue
        object_id = str(raw.get("objectId", ""))
        if not object_id:
            continue
        object_position = raw.get("position")
        agent_position = agent.get("position")
        agent_rotation = agent.get("rotation")
        horizon = agent.get("cameraHorizon")
        record_id = f"object:{object_id}"
        records[record_id] = ThorObjectMemoryRecord(
            record_id=record_id,
            object_id=object_id,
            object_type=str(raw.get("objectType", "Unknown")),
            object_position=(
                deepcopy(dict(object_position))
                if isinstance(object_position, Mapping)
                else None
            ),
            last_seen_agent_position=(
                deepcopy(dict(agent_position))
                if isinstance(agent_position, Mapping)
                else None
            ),
            last_seen_agent_rotation=(
                deepcopy(dict(agent_rotation))
                if isinstance(agent_rotation, Mapping)
                else None
            ),
            last_seen_camera_horizon=(
                float(horizon) if isinstance(horizon, (int, float)) else None
            ),
            last_seen_step=int(step),
            source_observation_id=str(observation_id),
        )
    return records


def build_thor_memory(kind: str) -> ThorMemoryProvider:
    """Construct a Phase 4 memory provider without a global-state fallback."""

    if kind == "no_memory":
        return NoThorMemory()
    if kind == "short_memory_k2":
        return ThorShortMemory(k=2)
    if kind == "object_memory":
        return ThorObjectMemory()
    raise ValueError(f"unsupported Phase 4 memory kind: {kind}")

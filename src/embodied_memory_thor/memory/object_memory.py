"""Persistent last-seen object memory derived only from visible observations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from embodied_memory_thor.env.object_parser import metadata_from_event, parse_objects


@dataclass
class ObjectMemoryRecord:
    """Latest visible state and provenance for one object instance."""

    object_id: str
    object_type: str
    last_seen_region: str | None
    last_seen_position: dict[str, Any] | None
    last_seen_step: int
    parent_receptacles: list[str]
    states: dict[str, bool]
    interactable_flags: dict[str, bool]
    source_observation_id: str
    status: str = "fresh"
    suspected_stale_step: int | None = None
    suspected_stale_region: str | None = None


class ObjectMemory:
    """Maintain persistent last-seen records without treating absence as deletion."""

    _STATE_FIELDS = ("isPickedUp", "isOpen", "isToggled", "isSliced", "isDirty")
    _FLAG_FIELDS = ("pickupable", "receptacle", "openable", "toggleable", "sliceable", "dirtyable")

    def __init__(self) -> None:
        self._records: dict[str, ObjectMemoryRecord] = {}

    def update(
        self,
        observation: Any,
        *,
        step: int,
        observation_id: str | None = None,
    ) -> list[str]:
        """Update records only for objects explicitly marked visible."""

        metadata = metadata_from_event(observation)
        agent_region = str(metadata.get("agent", {}).get("region", "")) or None
        source_id = observation_id or f"observation:{step}"
        updated: list[str] = []
        for obj in parse_objects(metadata, visible_only=True):
            object_id = str(obj.get("objectId", ""))
            if not object_id:
                continue
            object_region = str(obj.get("region") or agent_region or "") or None
            position = obj.get("position")
            self._records[object_id] = ObjectMemoryRecord(
                object_id=object_id,
                object_type=str(obj.get("objectType", "Unknown")),
                last_seen_region=object_region,
                last_seen_position=deepcopy(position) if isinstance(position, Mapping) else None,
                last_seen_step=int(step),
                parent_receptacles=[str(item) for item in obj.get("parentReceptacles", [])],
                states={field: bool(obj.get(field, False)) for field in self._STATE_FIELDS},
                interactable_flags={field: bool(obj.get(field, False)) for field in self._FLAG_FIELDS},
                source_observation_id=source_id,
            )
            updated.append(object_id)
        return updated

    def get(self, object_id: str) -> ObjectMemoryRecord | None:
        """Return a defensive record copy by object ID."""

        record = self._records.get(object_id)
        return deepcopy(record) if record is not None else None

    def retrieve(self, object_type: str, *, include_stale: bool = True) -> list[ObjectMemoryRecord]:
        """Return matching records, newest first."""

        expected = object_type.casefold()
        records = [
            record
            for record in self._records.values()
            if record.object_type.casefold() == expected
            and (include_stale or record.status != "suspected_stale")
        ]
        return deepcopy(sorted(records, key=lambda item: (-item.last_seen_step, item.object_id)))

    def mark_expected_region_miss(
        self,
        object_id: str,
        observation: Any,
        *,
        step: int,
    ) -> bool:
        """Mark stale only after observing the remembered region without the object."""

        record = self._records.get(object_id)
        if record is None or record.status == "suspected_stale":
            return False
        metadata = metadata_from_event(observation)
        current_region = str(metadata.get("agent", {}).get("region", "")) or None
        visible_ids = {obj["objectId"] for obj in parse_objects(metadata, visible_only=True)}
        if current_region != record.last_seen_region or object_id in visible_ids:
            return False
        record.status = "suspected_stale"
        record.suspected_stale_step = int(step)
        record.suspected_stale_region = current_region
        return True

    def snapshot(self) -> dict[str, Any]:
        """Return stable JSON-safe records keyed by object ID."""

        return {
            object_id: deepcopy(asdict(record))
            for object_id, record in sorted(self._records.items())
        }

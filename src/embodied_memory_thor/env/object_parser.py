"""Safe normalization helpers for AI2-THOR-style object metadata."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


OBJECT_FIELDS: tuple[str, ...] = (
    "objectType",
    "objectId",
    "position",
    "visible",
    "pickupable",
    "receptacle",
    "parentReceptacles",
    "receptacleObjectIds",
    "openable",
    "toggleable",
    "sliceable",
    "dirtyable",
    "isPickedUp",
    "isOpen",
    "isToggled",
    "isSliced",
    "isDirty",
)


DEFAULT_OBJECT_VALUES: dict[str, Any] = {
    "objectType": "Unknown",
    "objectId": "",
    "position": None,
    "visible": False,
    "pickupable": False,
    "receptacle": False,
    "parentReceptacles": [],
    "receptacleObjectIds": [],
    "openable": False,
    "toggleable": False,
    "sliceable": False,
    "dirtyable": False,
    "isPickedUp": False,
    "isOpen": False,
    "isToggled": False,
    "isSliced": False,
    "isDirty": False,
}


def parse_object(raw_object: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable subset of one object record with safe defaults."""

    parsed: dict[str, Any] = {}
    for field in OBJECT_FIELDS:
        value = raw_object.get(field, DEFAULT_OBJECT_VALUES[field])
        parsed[field] = deepcopy(value)

    for list_field in ("parentReceptacles", "receptacleObjectIds"):
        if parsed[list_field] is None:
            parsed[list_field] = []
        elif isinstance(parsed[list_field], (tuple, set)):
            parsed[list_field] = list(parsed[list_field])
        elif not isinstance(parsed[list_field], list):
            parsed[list_field] = [parsed[list_field]]

    return parsed


def metadata_from_event(event_or_metadata: Any) -> Mapping[str, Any]:
    """Extract metadata from an event object or accept a mapping directly."""

    if isinstance(event_or_metadata, Mapping):
        return event_or_metadata

    metadata = getattr(event_or_metadata, "metadata", None)
    if isinstance(metadata, Mapping):
        return metadata

    return {}


def parse_objects(event_or_metadata: Any, *, visible_only: bool = False) -> list[dict[str, Any]]:
    """Parse the object list in event metadata without assuming every field exists."""

    metadata = metadata_from_event(event_or_metadata)
    raw_objects = metadata.get("objects", [])
    if not isinstance(raw_objects, list):
        return []

    parsed = [parse_object(item) for item in raw_objects if isinstance(item, Mapping)]
    if visible_only:
        return [item for item in parsed if item["visible"]]
    return parsed

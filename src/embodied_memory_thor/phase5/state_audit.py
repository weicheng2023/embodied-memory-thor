"""Evaluator-only object-state comparison with tolerant pose semantics."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .anchors import stable_digest


LOGICAL_FIELDS = (
    "parentReceptacles",
    "isPickedUp",
    "isOpen",
    "isToggled",
    "isBroken",
    "isDirty",
    "isFilledWithLiquid",
)


def objects_from_metadata(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = metadata.get("objects", [])
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def build_object_snapshot(
    metadata: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for obj in objects_from_metadata(metadata):
        object_id = str(obj.get("objectId", ""))
        if not object_id or object_id in snapshot:
            raise ValueError("object metadata requires unique non-empty identifiers")
        snapshot[object_id] = {
            "position": deepcopy(obj.get("position")),
            "rotation": deepcopy(obj.get("rotation")),
            "parentReceptacles": deepcopy(obj.get("parentReceptacles")),
            "isMoving": obj.get("isMoving"),
            "isPickedUp": obj.get("isPickedUp"),
            "isOpen": obj.get("isOpen"),
            "isToggled": obj.get("isToggled"),
            "isBroken": obj.get("isBroken"),
            "isDirty": obj.get("isDirty"),
            "isFilledWithLiquid": obj.get("isFilledWithLiquid"),
        }
    return snapshot


def strict_snapshot_digest(snapshot: Mapping[str, Mapping[str, Any]]) -> str:
    return stable_digest(snapshot)


def logical_snapshot_digest(snapshot: Mapping[str, Mapping[str, Any]]) -> str:
    logical = {
        object_id: {field: state.get(field) for field in LOGICAL_FIELDS}
        for object_id, state in snapshot.items()
    }
    return stable_digest(logical)


def circular_angle_delta(left: float, right: float) -> float:
    """Return the smallest absolute Euler-component delta modulo 360 degrees."""

    return abs((left - right + 180.0) % 360.0 - 180.0)


def compare_object_snapshots(
    before: Mapping[str, Mapping[str, Any]],
    after: Mapping[str, Mapping[str, Any]],
    *,
    position_threshold: float,
    rotation_threshold: float,
) -> dict[str, Any]:
    if position_threshold < 0 or rotation_threshold < 0:
        raise ValueError("state comparison thresholds must be non-negative")
    before_ids = set(before)
    after_ids = set(after)
    shared = sorted(before_ids.intersection(after_ids))
    max_position_delta = 0.0
    max_rotation_delta = 0.0
    position_changed_count = 0
    rotation_changed_count = 0
    moving_changed_count = 0
    logical_changed_object_count = 0
    logical_changed_fields: set[str] = set()
    for object_id in shared:
        left = before[object_id]
        right = after[object_id]
        left_position = _vector(left.get("position"))
        right_position = _vector(right.get("position"))
        if left_position is None or right_position is None:
            position_delta = math.inf if left_position != right_position else 0.0
        else:
            position_delta = math.sqrt(
                sum(
                    (left_position[axis] - right_position[axis]) ** 2
                    for axis in ("x", "y", "z")
                )
            )
        max_position_delta = max(max_position_delta, position_delta)
        position_changed_count += int(position_delta > 0)

        left_rotation = _vector(left.get("rotation"))
        right_rotation = _vector(right.get("rotation"))
        if left_rotation is None or right_rotation is None:
            rotation_delta = math.inf if left_rotation != right_rotation else 0.0
        else:
            rotation_delta = max(
                circular_angle_delta(left_rotation[axis], right_rotation[axis])
                for axis in ("x", "y", "z")
            )
        max_rotation_delta = max(max_rotation_delta, rotation_delta)
        rotation_changed_count += int(rotation_delta > 0)
        moving_changed_count += int(left.get("isMoving") != right.get("isMoving"))
        changed_for_object = False
        for field in LOGICAL_FIELDS:
            if left.get(field) != right.get(field):
                logical_changed_fields.add(field)
                changed_for_object = True
        logical_changed_object_count += int(changed_for_object)

    strict_changed = strict_snapshot_digest(before) != strict_snapshot_digest(after)
    logical_changed = logical_snapshot_digest(before) != logical_snapshot_digest(after)
    material_change = bool(
        before_ids != after_ids
        or logical_changed
        or max_position_delta > position_threshold
        or max_rotation_delta > rotation_threshold
    )
    return {
        "strict_digest_before": strict_snapshot_digest(before),
        "strict_digest_after": strict_snapshot_digest(after),
        "logical_digest_before": logical_snapshot_digest(before),
        "logical_digest_after": logical_snapshot_digest(after),
        "strict_digest_changed": strict_changed,
        "logical_digest_changed": logical_changed,
        "material_change": material_change,
        "identity_set_changed": before_ids != after_ids,
        "object_count_before": len(before_ids),
        "object_count_after": len(after_ids),
        "position_changed_object_count": position_changed_count,
        "rotation_changed_object_count": rotation_changed_count,
        "is_moving_changed_object_count": moving_changed_count,
        "logical_changed_object_count": logical_changed_object_count,
        "logical_changed_field_categories": sorted(logical_changed_fields),
        "max_position_delta_meters": max_position_delta,
        "max_rotation_component_delta_degrees": max_rotation_delta,
        "strict_only_or_subthreshold_change": strict_changed and not material_change,
    }


def _vector(value: Any) -> dict[str, float] | None:
    if not isinstance(value, Mapping):
        return None
    try:
        result = {axis: float(value[axis]) for axis in ("x", "y", "z")}
    except (KeyError, TypeError, ValueError):
        return None
    return result if all(math.isfinite(number) for number in result.values()) else None

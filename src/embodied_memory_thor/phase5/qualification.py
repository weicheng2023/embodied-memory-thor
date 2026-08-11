"""Pure helpers for the evaluator-only real relocation qualification probe."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Mapping, Sequence


def spawn_coordinate_query(
    receptacle_object_id: str, *, anywhere: bool = False
) -> dict[str, Any]:
    if not receptacle_object_id.strip():
        raise ValueError("receptacle_object_id must be non-empty")
    return {
        "action": "GetSpawnCoordinatesAboveReceptacle",
        "objectId": receptacle_object_id,
        "anywhere": anywhere,
    }


def place_object_at_point_action(
    target_object_id: str, position: Mapping[str, Any]
) -> dict[str, Any]:
    if not target_object_id.strip():
        raise ValueError("target_object_id must be non-empty")
    normalized: dict[str, float] = {}
    for axis in ("x", "y", "z"):
        value = position.get(axis)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"position.{axis} must be numeric")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"position.{axis} must be finite")
        normalized[axis] = numeric
    return {
        "action": "PlaceObjectAtPoint",
        "objectId": target_object_id,
        "position": normalized,
    }


def assess_relocation_probe(
    *,
    target_object_id: str,
    before_position: Mapping[str, Any],
    spawn_query_success: bool,
    spawn_candidates: Sequence[Mapping[str, Any]],
    placement_success: bool,
    after_target: Mapping[str, Any] | None,
    immediate_visible_object_ids: Sequence[str],
    old_view_visible_object_ids: Sequence[str],
    stability_samples: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Assess already-collected evaluator evidence without touching a simulator."""

    reasons: list[str] = []
    if not spawn_query_success:
        reasons.append("spawn_coordinate_query_failed")
    if not spawn_candidates:
        reasons.append("no_spawn_candidates")
    if not placement_success:
        reasons.append("placement_action_failed")
    if after_target is None or str(after_target.get("objectId", "")) != target_object_id:
        reasons.append("same_target_not_found_after_placement")

    after_position = after_target.get("position", {}) if after_target else {}
    moved_distance = _xz_distance(before_position, after_position)
    if moved_distance is None or moved_distance <= 0.18:
        reasons.append("target_position_not_materially_changed")
    if target_object_id in set(immediate_visible_object_ids):
        reasons.append("target_visible_immediately_after_placement")
    if target_object_id in set(old_view_visible_object_ids):
        reasons.append("target_still_visible_from_old_viewpoint")
    if len(stability_samples) < 2:
        reasons.append("insufficient_stability_samples")
    elif not _positions_stable(stability_samples):
        reasons.append("target_not_stable_after_placement")

    return {
        "probe_contract": "phase5-relocation-qualification-v1",
        "planner_visible": False,
        "included_in_planner_metrics": False,
        "target_object_id": target_object_id,
        "moved_distance_xz_meters": moved_distance,
        "spawn_candidate_count": len(spawn_candidates),
        "stability_sample_count": len(stability_samples),
        "passed": not reasons,
        "rejection_reasons": reasons,
        "after_target": deepcopy(dict(after_target)) if after_target else None,
    }


def _xz_distance(a: Mapping[str, Any], b: Mapping[str, Any]) -> float | None:
    try:
        return math.hypot(float(a["x"]) - float(b["x"]), float(a["z"]) - float(b["z"]))
    except (KeyError, TypeError, ValueError):
        return None


def _positions_stable(samples: Sequence[Mapping[str, Any]]) -> bool:
    first = samples[0]
    return all(
        (distance := _xz_distance(first, sample)) is not None and distance <= 0.02
        for sample in samples[1:]
    )

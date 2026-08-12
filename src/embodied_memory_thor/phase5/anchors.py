"""Deterministic pre-qualified relocation anchor planning contracts."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any, Mapping, Sequence


SUPPORT_POLICY_VERSION = "phase5-r1-support-policy-v3"
ANCHOR_QUALIFICATION_VERSION = "phase5-anchor-qualification-v6"
ANCHOR_REGISTRY_VERSION = "phase5-private-anchor-registry-v6"
ANCHOR_GEOMETRY_VERSION = "phase5-axis-aware-rectangular-footprint-v2"
NATIVE_FIRST_CANDIDATE_POLICY_VERSION = "phase5-native-first-advisory-ranking-v1"
NATIVE_CANDIDATE_POLICY_VERSION = (
    "phase5-native-first-type-balanced-ranking-v2"
)
BOOK_SUPPORT_TYPE_ORDER = (
    "Bed",
    "CoffeeTable",
    "CounterTop",
    "Desk",
    "DiningTable",
    "Dresser",
    "Shelf",
    "SideTable",
)
BOOK_SUPPORT_TYPES = frozenset(BOOK_SUPPORT_TYPE_ORDER)
# Compatibility name for older imports. Policy v3 is semantic support
# eligibility, not a claim that every receptacle is geometrically open.
OPEN_SUPPORT_TYPES = BOOK_SUPPORT_TYPES


def stable_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_geometry_candidate_plan(
    *,
    target: Mapping[str, Any],
    support_queries: Sequence[Mapping[str, Any]],
    all_objects: Sequence[Mapping[str, Any]],
    minimum_move_meters: float = 0.5,
    footprint_margin_meters: float = 0.02,
) -> dict[str, Any]:
    """Filter and rank candidates before native placement outcomes are known."""

    if minimum_move_meters <= 0 or footprint_margin_meters < 0:
        raise ValueError("invalid anchor geometry thresholds")
    target_id = str(target.get("objectId", ""))
    before = _position(target)
    footprint_half_extents = _axis_aware_half_extents(target)
    if not target_id or before is None or footprint_half_extents is None:
        raise ValueError("target requires objectId, position, and AABB size")
    padded_half_x = footprint_half_extents["x"] + footprint_margin_meters
    padded_half_z = footprint_half_extents["z"] + footprint_margin_meters

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, float, float, float]] = set()
    for support_rank, query in enumerate(support_queries, start=1):
        support = query.get("support")
        coordinates = query.get("coordinates")
        if not isinstance(support, Mapping) or not isinstance(coordinates, Sequence):
            raise ValueError("support query requires support and coordinates")
        support_id = str(support.get("objectId", ""))
        if not support_id or support.get("objectType") not in BOOK_SUPPORT_TYPES:
            continue
        support_rect = _xz_rect(support)
        if support_rect is None:
            continue
        obstacles = [
            obj
            for obj in all_objects
            if str(obj.get("objectId", "")) not in {target_id, support_id}
            and support_id in {
                str(value) for value in (obj.get("parentReceptacles") or [])
            }
            and _xz_rect(obj) is not None
        ]
        obstacle_rects = [
            (str(obj.get("objectId", "")), _xz_rect(obj)) for obj in obstacles
        ]
        for raw_point in coordinates:
            point = _xyz(raw_point) if isinstance(raw_point, Mapping) else None
            if point is None:
                rejected.append(
                    {
                        "support_id": support_id,
                        "point": deepcopy(raw_point),
                        "reason": "non_numeric_xyz",
                    }
                )
                continue
            key = (
                support_id,
                round(point["x"], 6),
                round(point["y"], 6),
                round(point["z"], 6),
            )
            if key in seen:
                continue
            seen.add(key)
            movement = _xz_distance(before, point)
            if movement < minimum_move_meters:
                rejected.append(
                    {"support_id": support_id, "point": point, "reason": "move_too_small"}
                )
                continue
            footprint = (
                point["x"] - padded_half_x,
                point["x"] + padded_half_x,
                point["z"] - padded_half_z,
                point["z"] + padded_half_z,
            )
            edge_clearance = _contained_clearance(footprint, support_rect)
            if edge_clearance < 0:
                rejected.append(
                    {
                        "support_id": support_id,
                        "point": point,
                        "reason": "book_footprint_crosses_support_boundary",
                    }
                )
                continue
            collisions = [
                obstacle_id
                for obstacle_id, rectangle in obstacle_rects
                if rectangle is not None and _rectangles_overlap(footprint, rectangle)
            ]
            if collisions:
                rejected.append(
                    {
                        "support_id": support_id,
                        "point": point,
                        "reason": "book_footprint_overlaps_obstacle",
                        "obstacle_ids": sorted(collisions),
                    }
                )
                continue
            obstacle_clearance = min(
                (
                    _rectangle_clearance(footprint, rectangle)
                    for _, rectangle in obstacle_rects
                    if rectangle is not None
                ),
                default=edge_clearance,
            )
            accepted.append(
                {
                    "support_rank": support_rank,
                    "support_id": support_id,
                    "support_type": str(support.get("objectType", "")),
                    "point": point,
                    "movement_xz_meters": movement,
                    "edge_clearance_meters": edge_clearance,
                    "obstacle_clearance_meters": obstacle_clearance,
                    "clearance_score": min(edge_clearance, obstacle_clearance),
                }
            )

    accepted.sort(
        key=lambda item: (
            item["support_rank"],
            -item["clearance_score"],
            item["point"]["x"],
            item["point"]["z"],
        )
    )
    for index, item in enumerate(accepted, start=1):
        item["candidate_order"] = index
    return {
        "qualification_version": "phase5-anchor-qualification-v4",
        "geometry_version": ANCHOR_GEOMETRY_VERSION,
        "support_policy_version": SUPPORT_POLICY_VERSION,
        "orientation_policy": (
            "preserve_current_world_orientation_and_validate_native_placement"
        ),
        "selection_rule": (
            "support_rank_then_descending_geometry_clearance_then_xyz;"
            "first_fully_qualified_anchor"
        ),
        "minimum_move_meters": minimum_move_meters,
        "footprint_margin_meters": footprint_margin_meters,
        "target_object_id": target_id,
        "target_footprint_half_extents_meters": footprint_half_extents,
        "accepted_candidates": accepted,
        "geometry_rejections": rejected,
    }


def build_native_first_candidate_plan(
    *,
    target: Mapping[str, Any],
    support_queries: Sequence[Mapping[str, Any]],
    all_objects: Sequence[Mapping[str, Any]],
    minimum_move_meters: float = 0.5,
    footprint_margin_meters: float = 0.02,
) -> dict[str, Any]:
    """Rank query coordinates for native QA without geometry vetoing a trial."""

    if minimum_move_meters <= 0 or footprint_margin_meters < 0:
        raise ValueError("invalid native-first candidate thresholds")
    target_id = str(target.get("objectId", ""))
    before = _position(target)
    footprint_half_extents = _axis_aware_half_extents(target)
    if not target_id or before is None or footprint_half_extents is None:
        raise ValueError("target requires objectId, position, and AABB size")
    padded_half_x = footprint_half_extents["x"] + footprint_margin_meters
    padded_half_z = footprint_half_extents["z"] + footprint_margin_meters

    candidates: list[dict[str, Any]] = []
    hard_rejections: list[dict[str, Any]] = []
    seen: set[tuple[str, float, float, float]] = set()
    for support_rank, query in enumerate(support_queries, start=1):
        support = query.get("support")
        coordinates = query.get("coordinates")
        if not isinstance(support, Mapping) or not isinstance(coordinates, Sequence):
            raise ValueError("support query requires support and coordinates")
        support_id = str(support.get("objectId", ""))
        if not support_id or support.get("objectType") not in BOOK_SUPPORT_TYPES:
            continue
        support_rect = _xz_rect(support)
        obstacles = [
            obj
            for obj in all_objects
            if str(obj.get("objectId", "")) not in {target_id, support_id}
            and support_id in {
                str(value) for value in (obj.get("parentReceptacles") or [])
            }
            and _xz_rect(obj) is not None
        ]
        obstacle_rects = [
            (str(obj.get("objectId", "")), _xz_rect(obj)) for obj in obstacles
        ]
        for raw_point in coordinates:
            point = _xyz(raw_point) if isinstance(raw_point, Mapping) else None
            if point is None:
                hard_rejections.append(
                    {
                        "support_id": support_id,
                        "point": deepcopy(raw_point),
                        "reason": "non_numeric_xyz",
                    }
                )
                continue
            key = (
                support_id,
                round(point["x"], 6),
                round(point["y"], 6),
                round(point["z"], 6),
            )
            if key in seen:
                continue
            seen.add(key)
            movement = _xz_distance(before, point)
            if movement < minimum_move_meters:
                hard_rejections.append(
                    {"support_id": support_id, "point": point, "reason": "move_too_small"}
                )
                continue
            footprint = (
                point["x"] - padded_half_x,
                point["x"] + padded_half_x,
                point["z"] - padded_half_z,
                point["z"] + padded_half_z,
            )
            edge_clearance = (
                _contained_clearance(footprint, support_rect)
                if support_rect is not None
                else None
            )
            collisions = sorted(
                obstacle_id
                for obstacle_id, rectangle in obstacle_rects
                if rectangle is not None and _rectangles_overlap(footprint, rectangle)
            )
            boundary_passed = (
                edge_clearance is not None and edge_clearance >= 0
            )
            predicted_clear = boundary_passed and not collisions
            candidates.append(
                {
                    "support_rank": support_rank,
                    "support_id": support_id,
                    "support_type": str(support.get("objectType", "")),
                    "point": point,
                    "movement_xz_meters": movement,
                    "advisory_edge_clearance_meters": edge_clearance,
                    "advisory_boundary_passed": boundary_passed,
                    "advisory_obstacle_overlap_ids": collisions,
                    "advisory_obstacle_overlap_count": len(collisions),
                    "advisory_predicted_clear": predicted_clear,
                    "native_trial_required_for_acceptance": True,
                }
            )

    candidates.sort(
        key=lambda item: (
            0 if item["advisory_predicted_clear"] else 1,
            item["advisory_obstacle_overlap_count"],
            -(
                item["advisory_edge_clearance_meters"]
                if item["advisory_edge_clearance_meters"] is not None
                else -1e12
            ),
            item["support_rank"],
            item["point"]["x"],
            item["point"]["z"],
            item["point"]["y"],
        )
    )
    for index, item in enumerate(candidates, start=1):
        item["candidate_order"] = index
    return {
        "qualification_version": "phase5-anchor-qualification-v4",
        "geometry_version": ANCHOR_GEOMETRY_VERSION,
        "candidate_policy_version": NATIVE_FIRST_CANDIDATE_POLICY_VERSION,
        "support_policy_version": SUPPORT_POLICY_VERSION,
        "geometry_role": "advisory_pre_outcome_ranking_only",
        "native_placement_is_acceptance_authority": True,
        "boundary_prediction_is_hard_rejection": False,
        "obstacle_prediction_is_hard_rejection": False,
        "orientation_policy": "preserve_current_world_orientation_for_native_trial",
        "selection_rule": (
            "predicted_clear_then_overlap_count_then_descending_signed_edge_"
            "clearance_then_support_rank_then_xyz;first_fully_qualified_anchor"
        ),
        "hard_rejection_rule": "non_numeric_duplicate_or_move_below_minimum_only",
        "minimum_move_meters": minimum_move_meters,
        "footprint_margin_meters": footprint_margin_meters,
        "target_object_id": target_id,
        "target_footprint_half_extents_meters": footprint_half_extents,
        "accepted_candidates": candidates,
        "geometry_rejections": hard_rejections,
        "advisory_predicted_clear_count": sum(
            item["advisory_predicted_clear"] is True for item in candidates
        ),
        "advisory_boundary_crossing_count": sum(
            item["advisory_boundary_passed"] is False for item in candidates
        ),
        "advisory_obstacle_overlap_count": sum(
            item["advisory_obstacle_overlap_count"] > 0 for item in candidates
        ),
    }


def build_type_balanced_native_candidate_plan(
    *,
    target: Mapping[str, Any],
    support_queries: Sequence[Mapping[str, Any]],
    all_objects: Sequence[Mapping[str, Any]],
    minimum_move_meters: float = 0.5,
    footprint_margin_meters: float = 0.02,
) -> dict[str, Any]:
    """Round-robin semantic support types over the frozen v4 within-type rank."""

    base = build_native_first_candidate_plan(
        target=target,
        support_queries=support_queries,
        all_objects=all_objects,
        minimum_move_meters=minimum_move_meters,
        footprint_margin_meters=footprint_margin_meters,
    )
    grouped: dict[str, list[dict[str, Any]]] = {
        support_type: [] for support_type in BOOK_SUPPORT_TYPE_ORDER
    }
    for candidate in base["accepted_candidates"]:
        support_type = str(candidate["support_type"])
        if support_type in grouped:
            row = deepcopy(candidate)
            row["within_type_order"] = len(grouped[support_type]) + 1
            grouped[support_type].append(row)

    candidates: list[dict[str, Any]] = []
    present_types = [
        support_type
        for support_type in BOOK_SUPPORT_TYPE_ORDER
        if grouped[support_type]
    ]
    depth = 0
    while True:
        appended = False
        for support_type in present_types:
            rows = grouped[support_type]
            if depth < len(rows):
                candidates.append(rows[depth])
                appended = True
        if not appended:
            break
        depth += 1

    for index, item in enumerate(candidates, start=1):
        item["candidate_order"] = index
    return {
        **{
            key: deepcopy(value)
            for key, value in base.items()
            if key != "accepted_candidates"
        },
        "qualification_version": ANCHOR_QUALIFICATION_VERSION,
        "candidate_policy_version": NATIVE_CANDIDATE_POLICY_VERSION,
        "source_within_type_policy_version": (
            NATIVE_FIRST_CANDIDATE_POLICY_VERSION
        ),
        "selection_rule": (
            "round_robin_present_support_types_in_predeclared_semantic_order;"
            "within_each_type_use_native_first_advisory_ranking_v1;"
            "first_fully_qualified_anchor"
        ),
        "support_type_order": list(BOOK_SUPPORT_TYPE_ORDER),
        "present_support_types": present_types,
        "support_type_balancing_uses_native_outcomes": False,
        "accepted_candidates": candidates,
    }


def build_target_independent_coverage_route(
    *,
    reachable_positions: Sequence[Mapping[str, Any]],
    start_position: Mapping[str, Any],
    start_yaw: float,
    grid_size: float = 0.25,
    scan_spacing_steps: int = 3,
    scan_horizon_degrees: float = 0.0,
    start_camera_horizon_degrees: float | None = None,
    absolute_scan_horizon_degrees: float | None = None,
) -> dict[str, Any]:
    """Build a deterministic spaced-waypoint route without target/anchor input."""

    if grid_size <= 0 or scan_spacing_steps <= 0 or not reachable_positions:
        raise ValueError("coverage route requires positions and positive grid_size")
    if scan_horizon_degrees not in {0.0, 30.0}:
        raise ValueError("coverage scan horizon must be 0 or 30 degrees")
    if absolute_scan_horizon_degrees is not None and scan_horizon_degrees != 0.0:
        raise ValueError("absolute and relative horizon policies are mutually exclusive")
    horizon_setup: list[str] = []
    horizon_restore: list[str] = []
    if absolute_scan_horizon_degrees is not None:
        if start_camera_horizon_degrees is None:
            raise ValueError("absolute horizon policy requires the initial horizon")
        horizon_setup, horizon_restore = build_absolute_horizon_alignment_actions(
            start_horizon_degrees=start_camera_horizon_degrees,
            scan_horizon_degrees=absolute_scan_horizon_degrees,
        )
    nodes: dict[tuple[int, int], dict[str, float]] = {}
    for raw in reachable_positions:
        point = _xyz(raw)
        if point is None:
            continue
        key = (round(point["x"] / grid_size), round(point["z"] / grid_size))
        nodes.setdefault(key, point)
    start = _xyz(start_position)
    if start is None or not nodes:
        raise ValueError("coverage route has no valid start or nodes")
    start_key = min(nodes, key=lambda key: _xz_distance(start, nodes[key]))

    direction_order = (
        ((0, 1), 0.0, "north"),
        ((1, 0), 90.0, "east"),
        ((0, -1), 180.0, "south"),
        ((-1, 0), 270.0, "west"),
    )

    def neighbors(node: tuple[int, int]) -> list[tuple[int, int]]:
        return [
            (node[0] + delta[0], node[1] + delta[1])
            for delta, _, _ in direction_order
            if (node[0] + delta[0], node[1] + delta[1]) in nodes
        ]

    def shortest_path(
        source: tuple[int, int], destination: tuple[int, int]
    ) -> list[tuple[int, int]]:
        queue = [source]
        previous: dict[tuple[int, int], tuple[int, int] | None] = {source: None}
        for current in queue:
            if current == destination:
                break
            for neighbor in neighbors(current):
                if neighbor not in previous:
                    previous[neighbor] = current
                    queue.append(neighbor)
        if destination not in previous:
            raise ValueError("reachable-position graph is disconnected")
        result = [destination]
        while result[-1] != source:
            parent = previous[result[-1]]
            if parent is None:
                raise ValueError("coverage path reconstruction failed")
            result.append(parent)
        return list(reversed(result))

    distance_from_start = {
        node: len(shortest_path(start_key, node)) - 1 for node in nodes
    }
    uncovered = set(nodes)
    waypoints: list[tuple[int, int]] = []
    while uncovered:
        waypoint = min(
            uncovered,
            key=lambda node: (distance_from_start[node], node[0], node[1]),
        )
        waypoints.append(waypoint)
        covered = {
            node
            for node in uncovered
            if math.hypot(node[0] - waypoint[0], node[1] - waypoint[1])
            <= scan_spacing_steps
        }
        uncovered.difference_update(covered)

    ordered_waypoints = [start_key]
    remaining = set(waypoints)
    remaining.discard(start_key)
    current = start_key
    while remaining:
        destination = min(
            remaining,
            key=lambda node: (
                len(shortest_path(current, node)),
                distance_from_start[node],
                node[0],
                node[1],
            ),
        )
        ordered_waypoints.append(destination)
        remaining.remove(destination)
        current = destination

    actions: list[dict[str, Any]] = []
    yaw = float(start_yaw) % 360.0
    route_nodes = {start_key}

    def rotate_to(target_yaw: float, *, phase: str) -> None:
        nonlocal yaw
        delta_steps = round(((target_yaw - yaw) % 360.0) / 90.0) % 4
        if delta_steps == 3:
            actions.append({"action": {"action": "RotateLeft"}, "phase": phase})
            yaw = (yaw - 90.0) % 360.0
        else:
            for _ in range(delta_steps):
                actions.append({"action": {"action": "RotateRight"}, "phase": phase})
                yaw = (yaw + 90.0) % 360.0

    def full_scan(node: tuple[int, int]) -> None:
        nonlocal yaw
        for _ in range(4):
            actions.append(
                {
                    "action": {"action": "RotateRight"},
                    "phase": "coverage_scan",
                    "node": list(node),
                }
            )
            yaw = (yaw + 90.0) % 360.0

    if absolute_scan_horizon_degrees is not None:
        actions.extend(
            {
                "action": {"action": action_name},
                "phase": "coverage_absolute_horizon_alignment",
            }
            for action_name in horizon_setup
        )
    elif scan_horizon_degrees == 30.0:
        actions.append(
            {
                "action": {"action": "LookDown"},
                "phase": "coverage_horizon_setup",
            }
        )
    full_scan(start_key)
    current = start_key
    for waypoint_index, waypoint in enumerate(ordered_waypoints[1:], start=1):
        path = shortest_path(current, waypoint)
        for source, destination in zip(path, path[1:]):
            dx = destination[0] - source[0]
            dz = destination[1] - source[1]
            direction_row = next(
                (row for row in direction_order if row[0] == (dx, dz)), None
            )
            if direction_row is None:
                raise ValueError("coverage path contains a non-cardinal edge")
            _, target_yaw, direction = direction_row
            rotate_to(target_yaw, phase="coverage_orient")
            actions.append(
                {
                    "action": {"action": "MoveAhead"},
                    "phase": "coverage_move",
                    "from_node": list(source),
                    "to_node": list(destination),
                    "direction": direction,
                    "waypoint_index": waypoint_index,
                }
            )
            route_nodes.add(destination)
        full_scan(waypoint)
        current = waypoint
    if absolute_scan_horizon_degrees is not None:
        actions.extend(
            {
                "action": {"action": action_name},
                "phase": "coverage_initial_horizon_restore",
            }
            for action_name in horizon_restore
        )
    elif scan_horizon_degrees == 30.0:
        actions.append(
            {
                "action": {"action": "LookUp"},
                "phase": "coverage_horizon_restore",
            }
        )
    route = {
        "route_version": (
            "phase5-target-independent-absolute-horizon-v4"
            if absolute_scan_horizon_degrees is not None
            else "phase5-target-independent-downward-scan-v3"
            if scan_horizon_degrees == 30.0
            else "phase5-target-independent-spaced-waypoints-v2"
        ),
        "target_or_anchor_input_used": False,
        "grid_size": grid_size,
        "scan_spacing_steps": scan_spacing_steps,
        "nominal_scan_spacing_meters": scan_spacing_steps * grid_size,
        "start_node": list(start_key),
        "reachable_node_count": len(nodes),
        "scan_waypoint_count": len(ordered_waypoints),
        "visited_node_count": len(route_nodes),
        "all_nodes_within_nominal_scan_radius": all(
            min(
                math.hypot(node[0] - waypoint[0], node[1] - waypoint[1])
                for waypoint in ordered_waypoints
            )
            <= scan_spacing_steps
            for node in nodes
        ),
        "complete_graph_coverage": True,
        "actions": actions,
    }
    if absolute_scan_horizon_degrees is not None:
        route["initial_camera_horizon_degrees"] = float(
            start_camera_horizon_degrees
        )
        route["absolute_scan_horizon_degrees"] = float(
            absolute_scan_horizon_degrees
        )
        route["horizon_alignment_action_count"] = len(horizon_setup)
        route["horizon_restoration_action_count"] = len(horizon_restore)
        route["camera_horizon_restored_at_route_end"] = True
    elif scan_horizon_degrees == 30.0:
        route["scan_horizon_degrees"] = 30.0
        route["camera_horizon_restored_at_route_end"] = True
    return route


def build_absolute_horizon_alignment_actions(
    *,
    start_horizon_degrees: float,
    scan_horizon_degrees: float = 0.0,
    step_degrees: float = 30.0,
) -> tuple[list[str], list[str]]:
    """Return bounded ordinary actions to reach and restore one absolute horizon."""

    values = (start_horizon_degrees, scan_horizon_degrees, step_degrees)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("camera horizons must be finite")
    if step_degrees <= 0:
        raise ValueError("camera horizon step must be positive")
    if start_horizon_degrees < -30.0 or start_horizon_degrees > 60.0:
        raise ValueError("initial camera horizon is outside the supported range")
    if scan_horizon_degrees < -30.0 or scan_horizon_degrees > 60.0:
        raise ValueError("absolute scan horizon is outside the supported range")
    raw_steps = (scan_horizon_degrees - start_horizon_degrees) / step_degrees
    rounded_steps = round(raw_steps)
    if not math.isclose(raw_steps, rounded_steps, abs_tol=1e-9):
        raise ValueError("camera horizon difference must match the action step")
    if abs(rounded_steps) > 3:
        raise ValueError("camera horizon alignment exceeds the bounded action count")
    if rounded_steps > 0:
        setup = ["LookDown"] * rounded_steps
    else:
        setup = ["LookUp"] * abs(rounded_steps)
    inverse = {"LookDown": "LookUp", "LookUp": "LookDown"}
    restore = [inverse[action] for action in reversed(setup)]
    return setup, restore


def public_anchor_reference(
    *, anchor_id: str, private_registry_digest: str, coverage_route_digest: str
) -> dict[str, str]:
    """Return the only anchor fields allowed in an ordinary manifest."""

    for label, value in (
        ("anchor_id", anchor_id),
        ("private_registry_digest", private_registry_digest),
        ("coverage_route_digest", coverage_route_digest),
    ):
        if not value.strip():
            raise ValueError(f"{label} must be non-empty")
    return {
        "anchor_id": anchor_id,
        "private_registry_digest": private_registry_digest,
        "coverage_route_digest": coverage_route_digest,
    }


def _xyz(value: Mapping[str, Any]) -> dict[str, float] | None:
    try:
        result = {axis: float(value[axis]) for axis in ("x", "y", "z")}
    except (KeyError, TypeError, ValueError):
        return None
    return result if all(math.isfinite(number) for number in result.values()) else None


def _position(obj: Mapping[str, Any]) -> dict[str, float] | None:
    raw = obj.get("position")
    return _xyz(raw) if isinstance(raw, Mapping) else None


def _axis_aware_half_extents(obj: Mapping[str, Any]) -> dict[str, float] | None:
    bounds = obj.get("axisAlignedBoundingBox")
    size = bounds.get("size") if isinstance(bounds, Mapping) else None
    if not isinstance(size, Mapping):
        return None
    try:
        half_extents = {
            "x": float(size["x"]) / 2.0,
            "z": float(size["z"]) / 2.0,
        }
    except (KeyError, TypeError, ValueError):
        return None
    if not all(
        math.isfinite(value) and value > 0 for value in half_extents.values()
    ):
        return None
    return half_extents


def _xz_rect(obj: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    bounds = obj.get("axisAlignedBoundingBox")
    center = bounds.get("center") if isinstance(bounds, Mapping) else None
    size = bounds.get("size") if isinstance(bounds, Mapping) else None
    if not isinstance(center, Mapping) or not isinstance(size, Mapping):
        return None
    try:
        half_x = float(size["x"]) / 2.0
        half_z = float(size["z"]) / 2.0
        x = float(center["x"])
        z = float(center["z"])
    except (KeyError, TypeError, ValueError):
        return None
    return (x - half_x, x + half_x, z - half_z, z + half_z)


def _contained_clearance(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
) -> float:
    return min(
        inner[0] - outer[0],
        outer[1] - inner[1],
        inner[2] - outer[2],
        outer[3] - inner[3],
    )


def _rectangles_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    return a[0] < b[1] and a[1] > b[0] and a[2] < b[3] and a[3] > b[2]


def _rectangle_clearance(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    dx = max(b[0] - a[1], a[0] - b[1], 0.0)
    dz = max(b[2] - a[3], a[2] - b[3], 0.0)
    return math.hypot(dx, dz)


def _xz_distance(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["z"]) - float(b["z"]))

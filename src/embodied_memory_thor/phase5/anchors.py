"""Deterministic pre-qualified relocation anchor planning contracts."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any, Mapping, Sequence


ANCHOR_QUALIFICATION_VERSION = "phase5-anchor-qualification-v1"
ANCHOR_REGISTRY_VERSION = "phase5-private-anchor-registry-v1"
OPEN_SUPPORT_TYPES = frozenset(
    {"CounterTop", "DiningTable", "CoffeeTable", "SideTable", "Desk"}
)


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
    footprint_half_extent = _conservative_half_extent(target)
    if not target_id or before is None or footprint_half_extent is None:
        raise ValueError("target requires objectId, position, and AABB size")
    padded_half_extent = footprint_half_extent + footprint_margin_meters

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, float, float, float]] = set()
    for support_rank, query in enumerate(support_queries, start=1):
        support = query.get("support")
        coordinates = query.get("coordinates")
        if not isinstance(support, Mapping) or not isinstance(coordinates, Sequence):
            raise ValueError("support query requires support and coordinates")
        support_id = str(support.get("objectId", ""))
        if not support_id or support.get("objectType") not in OPEN_SUPPORT_TYPES:
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
                point["x"] - padded_half_extent,
                point["x"] + padded_half_extent,
                point["z"] - padded_half_extent,
                point["z"] + padded_half_extent,
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
        "qualification_version": ANCHOR_QUALIFICATION_VERSION,
        "selection_rule": (
            "support_rank_then_descending_geometry_clearance_then_xyz;"
            "first_fully_qualified_anchor"
        ),
        "minimum_move_meters": minimum_move_meters,
        "footprint_margin_meters": footprint_margin_meters,
        "target_object_id": target_id,
        "target_footprint_half_extent_meters": footprint_half_extent,
        "accepted_candidates": accepted,
        "geometry_rejections": rejected,
    }


def build_target_independent_coverage_route(
    *,
    reachable_positions: Sequence[Mapping[str, Any]],
    start_position: Mapping[str, Any],
    start_yaw: float,
    grid_size: float = 0.25,
    scan_spacing_steps: int = 3,
    scan_horizon_degrees: float = 0.0,
) -> dict[str, Any]:
    """Build a deterministic spaced-waypoint route without target/anchor input."""

    if grid_size <= 0 or scan_spacing_steps <= 0 or not reachable_positions:
        raise ValueError("coverage route requires positions and positive grid_size")
    if scan_horizon_degrees not in {0.0, 30.0}:
        raise ValueError("coverage scan horizon must be 0 or 30 degrees")
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

    if scan_horizon_degrees == 30.0:
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
    if scan_horizon_degrees == 30.0:
        actions.append(
            {
                "action": {"action": "LookUp"},
                "phase": "coverage_horizon_restore",
            }
        )
    route = {
        "route_version": (
            "phase5-target-independent-downward-scan-v3"
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
    if scan_horizon_degrees == 30.0:
        route["scan_horizon_degrees"] = 30.0
        route["camera_horizon_restored_at_route_end"] = True
    return route


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


def _conservative_half_extent(obj: Mapping[str, Any]) -> float | None:
    bounds = obj.get("axisAlignedBoundingBox")
    size = bounds.get("size") if isinstance(bounds, Mapping) else None
    if not isinstance(size, Mapping):
        return None
    try:
        return max(float(size["x"]), float(size["z"])) / 2.0
    except (KeyError, TypeError, ValueError):
        return None


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

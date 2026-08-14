"""Target-independent budgeted visual fallback construction for Phase 5 R2."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from typing import Any

from .anchors import (
    build_absolute_horizon_alignment_actions,
    normalize_absolute_horizon_degrees,
    stable_digest,
)


BUDGETED_VISUAL_FALLBACK_POLICY_VERSION = "phase5-r2-budgeted-visual-fallback-v1"
BUDGETED_VISUAL_FALLBACK_SELECTION_POLICY = "deterministic-grid-binning-v1"
BUDGETED_VISUAL_FALLBACK_BIN_SIZE_STEPS = 3
BUDGETED_VISUAL_FALLBACK_ACTION_LIMIT = 2048

_DIRECTIONS = (
    ((0, 1), 0.0, "north"),
    ((1, 0), 90.0, "east"),
    ((0, -1), 180.0, "south"),
    ((-1, 0), 270.0, "west"),
)


class BudgetedVisualFallbackConstructionError(ValueError):
    """Fail-closed over-budget result with coordinate-free audit metrics."""

    def __init__(self, message: str, route: Mapping[str, Any]) -> None:
        super().__init__(message)
        self.route = dict(route)


def _coordinate(value: Mapping[str, Any], name: str) -> float | None:
    try:
        return float(value[name])
    except (KeyError, TypeError, ValueError):
        return None


def _shortest_path(
    start: tuple[int, int],
    goal: tuple[int, int],
    nodes: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    if start == goal:
        return [start]
    parents: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    pending = deque([start])
    while pending:
        current = pending.popleft()
        for (dx, dz), _, _ in _DIRECTIONS:
            neighbor = (current[0] + dx, current[1] + dz)
            if neighbor not in nodes or neighbor in parents:
                continue
            parents[neighbor] = current
            if neighbor == goal:
                path = [goal]
                while path[-1] != start:
                    parent = parents[path[-1]]
                    if parent is None:  # pragma: no cover - guarded by loop condition
                        raise RuntimeError("shortest-path parent chain ended early")
                    path.append(parent)
                return list(reversed(path))
            pending.append(neighbor)
    raise ValueError("budgeted visual fallback reachable-position graph is disconnected")


def build_target_independent_budgeted_visual_fallback_route(
    *,
    reachable_positions: Sequence[Mapping[str, Any]],
    start_position: Mapping[str, Any],
    start_yaw: float,
    start_camera_horizon_degrees: float,
    grid_size: float = 0.25,
    bin_size_steps: int = BUDGETED_VISUAL_FALLBACK_BIN_SIZE_STEPS,
    action_limit: int = BUDGETED_VISUAL_FALLBACK_ACTION_LIMIT,
) -> dict[str, Any]:
    """Build a deterministic, target-free sampled scan route.

    Reachable nodes are partitioned into fixed grid bins. One deterministic
    reachable representative is selected per occupied bin, with the start node
    retained for its bin. Representatives are joined by deterministic shortest
    graph paths. No object, outcome, memory, or variant input is accepted.
    """

    if grid_size <= 0 or bin_size_steps <= 0 or action_limit <= 0:
        raise ValueError("budgeted visual fallback requires positive fixed parameters")
    nodes: set[tuple[int, int]] = set()
    for raw in reachable_positions:
        x = _coordinate(raw, "x")
        z = _coordinate(raw, "z")
        if x is not None and z is not None:
            nodes.add((round(x / grid_size), round(z / grid_size)))
    start_x = _coordinate(start_position, "x")
    start_z = _coordinate(start_position, "z")
    if not nodes or start_x is None or start_z is None:
        raise ValueError("budgeted visual fallback has no valid start or nodes")
    continuous_start = (start_x / grid_size, start_z / grid_size)
    start_key = min(
        nodes,
        key=lambda key: (
            (key[0] - continuous_start[0]) ** 2 + (key[1] - continuous_start[1]) ** 2,
            key,
        ),
    )

    # A disconnected export cannot support a single executable shared route.
    reached = {start_key}
    pending = deque([start_key])
    while pending:
        current = pending.popleft()
        for (dx, dz), _, _ in _DIRECTIONS:
            neighbor = (current[0] + dx, current[1] + dz)
            if neighbor in nodes and neighbor not in reached:
                reached.add(neighbor)
                pending.append(neighbor)
    if reached != nodes:
        raise ValueError("budgeted visual fallback reachable-position graph is disconnected")

    min_x = min(key[0] for key in nodes)
    min_z = min(key[1] for key in nodes)

    def bin_key(node: tuple[int, int]) -> tuple[int, int]:
        return (
            (node[0] - min_x) // bin_size_steps,
            (node[1] - min_z) // bin_size_steps,
        )

    bins: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for node in sorted(nodes):
        bins.setdefault(bin_key(node), []).append(node)
    start_bin = bin_key(start_key)
    representatives: dict[tuple[int, int], tuple[int, int]] = {}
    for key, members in sorted(bins.items()):
        if key == start_bin:
            representatives[key] = start_key
            continue
        center_twice = (
            2 * min_x + (2 * key[0] + 1) * bin_size_steps - 1,
            2 * min_z + (2 * key[1] + 1) * bin_size_steps - 1,
        )
        representatives[key] = min(
            members,
            key=lambda node: (
                (2 * node[0] - center_twice[0]) ** 2
                + (2 * node[1] - center_twice[1]) ** 2,
                node,
            ),
        )

    remaining = set(representatives.values()) - {start_key}
    viewpoint_order = [start_key]
    route_paths: list[list[tuple[int, int]]] = []
    current = start_key
    while remaining:
        candidates: list[tuple[int, tuple[int, int], list[tuple[int, int]]]] = []
        for candidate in sorted(remaining):
            path = _shortest_path(current, candidate, nodes)
            candidates.append((len(path) - 1, candidate, path))
        _, selected, path = min(candidates, key=lambda row: (row[0], row[1]))
        route_paths.append(path)
        viewpoint_order.append(selected)
        remaining.remove(selected)
        current = selected

    normalized_horizon = normalize_absolute_horizon_degrees(
        start_camera_horizon_degrees
    )
    horizon_setup, horizon_restore = build_absolute_horizon_alignment_actions(
        start_horizon_degrees=normalized_horizon,
        scan_horizon_degrees=0.0,
    )
    actions: list[dict[str, Any]] = [
        {
            "action": {"action": action_name},
            "phase": "budgeted_visual_fallback_initial_horizon_alignment",
        }
        for action_name in horizon_setup
    ]
    yaw = float(start_yaw) % 360.0

    def rotate_to(target_yaw: float) -> None:
        nonlocal yaw
        delta_steps = round(((target_yaw - yaw) % 360.0) / 90.0) % 4
        if delta_steps == 3:
            actions.append(
                {
                    "action": {"action": "RotateLeft"},
                    "phase": "budgeted_visual_fallback_traverse_orient",
                }
            )
            yaw = (yaw - 90.0) % 360.0
        else:
            for _ in range(delta_steps):
                actions.append(
                    {
                        "action": {"action": "RotateRight"},
                        "phase": "budgeted_visual_fallback_traverse_orient",
                    }
                )
                yaw = (yaw + 90.0) % 360.0

    def scan(viewpoint_index: int) -> None:
        nonlocal yaw
        for horizon, phase in (
            (0.0, "budgeted_visual_fallback_scan_zero"),
            (30.0, "budgeted_visual_fallback_scan_downward"),
        ):
            if horizon == 30.0:
                actions.append(
                    {
                        "action": {"action": "LookDown"},
                        "phase": "budgeted_visual_fallback_horizon_down",
                        "viewpoint_index": viewpoint_index,
                    }
                )
            for _ in range(4):
                actions.append(
                    {
                        "action": {"action": "RotateRight"},
                        "phase": phase,
                        "viewpoint_index": viewpoint_index,
                        "scan_horizon_degrees": horizon,
                    }
                )
                yaw = (yaw + 90.0) % 360.0
            if horizon == 30.0:
                actions.append(
                    {
                        "action": {"action": "LookUp"},
                        "phase": "budgeted_visual_fallback_horizon_zero",
                        "viewpoint_index": viewpoint_index,
                    }
                )

    move_count = 0
    scan(1)
    for viewpoint_index, path in enumerate(route_paths, start=2):
        for source, destination in zip(path, path[1:]):
            delta = (destination[0] - source[0], destination[1] - source[1])
            direction = next(
                (entry for entry in _DIRECTIONS if entry[0] == delta), None
            )
            if direction is None:  # pragma: no cover - shortest path is cardinal
                raise RuntimeError("budgeted route contains a non-cardinal edge")
            rotate_to(direction[1])
            actions.append(
                {
                    "action": {"action": "MoveAhead"},
                    "phase": "budgeted_visual_fallback_traverse_move",
                    "direction": direction[2],
                }
            )
            move_count += 1
        scan(viewpoint_index)
    actions.extend(
        {
            "action": {"action": action_name},
            "phase": "budgeted_visual_fallback_initial_horizon_restore",
        }
        for action_name in horizon_restore
    )
    max_bin_distance = max(
        max(
            abs(node[0] - representatives[bin_key(node)][0]),
            abs(node[1] - representatives[bin_key(node)][1]),
        )
        for node in nodes
    )
    route: dict[str, Any] = {
        "route_version": BUDGETED_VISUAL_FALLBACK_POLICY_VERSION,
        "viewpoint_selection_policy": BUDGETED_VISUAL_FALLBACK_SELECTION_POLICY,
        "target_or_anchor_input_used": False,
        "qualification_goal_input_used": False,
        "memory_input_used": False,
        "memory_variant_input_used": False,
        "candidate_outcome_input_used": False,
        "grid_size": grid_size,
        "bin_size_steps": bin_size_steps,
        "action_limit": action_limit,
        "action_count": len(actions),
        "reachable_node_count": len(nodes),
        "viewpoint_count": len(viewpoint_order),
        "traverse_move_count": move_count,
        "scan_horizons_degrees": [0.0, 30.0],
        "full_cardinal_scans_per_viewpoint": 2,
        "initial_camera_horizon_degrees": normalized_horizon,
        "camera_horizon_restored_at_route_end": True,
        "coverage_summary": {
            "occupied_bin_count": len(bins),
            "occupied_bins_with_viewpoint_count": len(representatives),
            "all_occupied_bins_represented": len(bins) == len(representatives),
            "maximum_within_bin_grid_chebyshev_distance": max_bin_distance,
            "line_of_sight_coverage_claimed": False,
        },
        "actions": actions,
    }
    route["route_digest"] = stable_digest(route)
    if len(actions) > action_limit:
        raise BudgetedVisualFallbackConstructionError(
            "budgeted visual fallback action limit exceeded: "
            f"{len(actions)}>{action_limit}",
            route,
        )
    return route

"""Evaluator-only route construction helpers for the ordered R2 task."""

from __future__ import annotations

import math
from collections import deque
from typing import Any, Mapping, Sequence

from embodied_memory_thor.phase5.anchors import stable_digest


R2_QUALIFICATION_VERSION = "phase5-r2-native-qualification-v1"
R2_SUBGOAL_ROUTE_VERSION = "phase5-r2-task-subgoal-navigation-v1"


def normalize_interactable_pose(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """Normalize an AI2-THOR interactable pose to TeleportFull arguments."""

    try:
        rotation = raw.get("rotation", 0.0)
        if isinstance(rotation, Mapping):
            rotation = rotation.get("y", 0.0)
        return {
            "x": float(raw["x"]),
            "y": float(raw["y"]),
            "z": float(raw["z"]),
            "rotation": float(rotation) % 360.0,
            "horizon": float(raw.get("horizon", raw.get("cameraHorizon", 0.0))),
            "standing": bool(raw.get("standing", True)),
        }
    except (KeyError, TypeError, ValueError):
        return None


def pose_sort_key(pose: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        float(pose["x"]),
        float(pose["z"]),
        float(pose["rotation"]),
        float(pose["horizon"]),
        not bool(pose["standing"]),
        float(pose["y"]),
    )


def _cardinal_steps(
    *, current: float, target: float, tolerance_degrees: float = 1.0
) -> tuple[list[str], float]:
    delta = (float(target) - float(current)) % 360.0
    steps = round(delta / 90.0) % 4
    if abs(delta - (steps * 90.0) % 360.0) > tolerance_degrees:
        raise ValueError("route yaw is not aligned to the 90-degree action grid")
    if steps == 3:
        return ["RotateLeft"], (float(current) - 90.0) % 360.0
    return ["RotateRight"] * steps, (float(current) + 90.0 * steps) % 360.0


def _horizon_steps(
    *, current: float, target: float, tolerance_degrees: float = 0.01
) -> list[str]:
    delta = float(target) - float(current)
    steps = round(delta / 30.0)
    if abs(delta - steps * 30.0) > tolerance_degrees:
        raise ValueError("route horizon is not aligned to 30-degree look actions")
    action = "LookDown" if steps > 0 else "LookUp"
    return [action] * abs(steps)


def _grid_graph(
    reachable_positions: Sequence[Mapping[str, Any]], *, grid_size: float
) -> dict[tuple[int, int], dict[str, float]]:
    if grid_size <= 0:
        raise ValueError("grid_size must be positive")
    nodes: dict[tuple[int, int], dict[str, float]] = {}
    for raw in reachable_positions:
        try:
            point = {
                "x": float(raw["x"]),
                "y": float(raw.get("y", 0.0)),
                "z": float(raw["z"]),
            }
        except (KeyError, TypeError, ValueError):
            continue
        key = (round(point["x"] / grid_size), round(point["z"] / grid_size))
        nodes.setdefault(key, point)
    if not nodes:
        raise ValueError("reachable-position graph is empty")
    return nodes


def _nearest_node(
    nodes: Mapping[tuple[int, int], Mapping[str, float]],
    pose: Mapping[str, Any],
    *,
    maximum_distance: float,
) -> tuple[int, int]:
    try:
        x = float(pose["x"])
        z = float(pose["z"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("route pose has no finite x/z") from exc
    node = min(
        nodes,
        key=lambda key: math.hypot(
            float(nodes[key]["x"]) - x,
            float(nodes[key]["z"]) - z,
        ),
    )
    distance = math.hypot(
        float(nodes[node]["x"]) - x,
        float(nodes[node]["z"]) - z,
    )
    if distance > maximum_distance:
        raise ValueError("interactable pose is not on the reachable-position grid")
    return node


def shortest_grid_path(
    *,
    reachable_positions: Sequence[Mapping[str, Any]],
    start_pose: Mapping[str, Any],
    destination_pose: Mapping[str, Any],
    grid_size: float = 0.25,
) -> list[tuple[int, int]]:
    """Return a deterministic cardinal shortest path between two poses."""

    nodes = _grid_graph(reachable_positions, grid_size=grid_size)
    tolerance = grid_size * 0.51
    start = _nearest_node(nodes, start_pose, maximum_distance=tolerance)
    destination = _nearest_node(
        nodes, destination_pose, maximum_distance=tolerance
    )
    direction_order = ((0, 1), (1, 0), (0, -1), (-1, 0))
    queue: deque[tuple[int, int]] = deque([start])
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    while queue:
        current = queue.popleft()
        if current == destination:
            break
        for dx, dz in direction_order:
            neighbor = (current[0] + dx, current[1] + dz)
            if neighbor in nodes and neighbor not in previous:
                previous[neighbor] = current
                queue.append(neighbor)
    if destination not in previous:
        raise ValueError("R2 start and subgoal poses are disconnected")
    path = [destination]
    while path[-1] != start:
        parent = previous[path[-1]]
        if parent is None:
            raise ValueError("R2 shortest-path reconstruction failed")
        path.append(parent)
    return list(reversed(path))


def build_task_subgoal_route(
    *,
    reachable_positions: Sequence[Mapping[str, Any]],
    start_pose: Mapping[str, Any],
    destination_pose: Mapping[str, Any],
    grid_size: float = 0.25,
) -> dict[str, Any]:
    """Build a goal-qualified but coordinate-free-at-runtime primitive route."""

    path = shortest_grid_path(
        reachable_positions=reachable_positions,
        start_pose=start_pose,
        destination_pose=destination_pose,
        grid_size=grid_size,
    )
    yaw = float(start_pose["rotation"]) % 360.0
    actions: list[dict[str, Any]] = []
    direction_yaw = {
        (0, 1): 0.0,
        (1, 0): 90.0,
        (0, -1): 180.0,
        (-1, 0): 270.0,
    }
    for source, destination in zip(path, path[1:]):
        delta = (destination[0] - source[0], destination[1] - source[1])
        if delta not in direction_yaw:
            raise ValueError("R2 shortest path contains a non-cardinal edge")
        rotations, yaw = _cardinal_steps(
            current=yaw, target=direction_yaw[delta]
        )
        actions.extend(
            {"action": {"action": name}, "phase": "subgoal_orient"}
            for name in rotations
        )
        actions.append(
            {
                "action": {"action": "MoveAhead"},
                "phase": "subgoal_move",
                "from_node": list(source),
                "to_node": list(destination),
            }
        )
    final_rotations, yaw = _cardinal_steps(
        current=yaw, target=float(destination_pose["rotation"])
    )
    actions.extend(
        {"action": {"action": name}, "phase": "subgoal_final_orient"}
        for name in final_rotations
    )
    horizon_actions = _horizon_steps(
        current=float(start_pose.get("horizon", 0.0)),
        target=float(destination_pose.get("horizon", 0.0)),
    )
    actions.extend(
        {"action": {"action": name}, "phase": "subgoal_final_horizon"}
        for name in horizon_actions
    )
    route = {
        "route_version": R2_SUBGOAL_ROUTE_VERSION,
        "route_role": "task_subgoal_navigation",
        "qualification_goal_input_used": True,
        "target_or_anchor_input_used": True,
        "runtime_coordinate_input_used": False,
        "grid_size": grid_size,
        "path_node_count": len(path),
        "actions": actions,
    }
    route["route_digest"] = stable_digest(route)
    return route


def route_action_codes(route: Mapping[str, Any]) -> str:
    name_to_code = {
        "LookDown": "D",
        "MoveAhead": "F",
        "RotateLeft": "L",
        "RotateRight": "R",
        "LookUp": "U",
    }
    raw_actions = route.get("actions", [])
    if not isinstance(raw_actions, list):
        raise ValueError("route actions must be a list")
    codes: list[str] = []
    for row in raw_actions:
        action = row.get("action", {}) if isinstance(row, Mapping) else {}
        name = action.get("action") if isinstance(action, Mapping) else None
        if name not in name_to_code:
            raise ValueError(f"unsupported frozen R2 route action: {name!r}")
        codes.append(name_to_code[name])
    if not codes:
        raise ValueError("frozen R2 route cannot be empty")
    return "".join(codes)

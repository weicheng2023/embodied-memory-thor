#!/usr/bin/env python3
"""Batch-check R1 starts and frozen route limits after the initial six."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase5.anchors import (  # noqa: E402
    build_target_independent_coverage_route,
    stable_digest,
)
from qualify_phase5_r1_starts import (  # noqa: E402
    CONTROLLER_SETTINGS,
    _book,
    _digest,
    _git_state,
    _normalize_pose,
    _package_version,
    _visible,
    _write_json,
)


SCRIPT_VERSION = "phase5-r1-remaining-prescreen-v1"
BOUNDARY = "EVALUATOR-ONLY PRIVATE START REGISTRY - NEVER PLANNER INPUT"
INITIAL_BATCH_SIZE = 6
ROUTE_ACTION_LIMIT = 240


def _ordered_presence_scenes(census: Mapping[str, Any]) -> list[str]:
    raw = census.get("presence_passed_scenes_in_declared_order")
    if not isinstance(raw, list):
        gate = census.get("presence_gate", {})
        raw = gate.get("passed_scenes_in_declared_order") if isinstance(gate, Mapping) else None
    scenes = [str(scene) for scene in raw] if isinstance(raw, list) else []
    if len(scenes) != 35 or len(set(scenes)) != len(scenes):
        raise ValueError("census must retain the frozen 35-scene presence order")
    return scenes


def _sorted_interactable_poses(controller: Any, object_id: str) -> list[dict[str, Any]]:
    event = controller.step(action="GetInteractablePoses", objectId=object_id)
    if event.metadata.get("lastActionSuccess") is not True:
        raise RuntimeError(
            "GetInteractablePoses failed: " + str(event.metadata.get("errorMessage", ""))
        )
    raw_poses = event.metadata.get("actionReturn") or []
    return sorted(
        (
            pose
            for pose in (
                _normalize_pose(raw)
                for raw in raw_poses
                if isinstance(raw, Mapping)
            )
            if pose is not None
        ),
        key=lambda pose: (
            pose["x"],
            pose["z"],
            pose["rotation"],
            pose["horizon"],
            not pose["standing"],
            pose["y"],
        ),
    )


def _qualify_start(
    controller: Any, *, scene: str, max_pose_trials: int
) -> dict[str, Any]:
    reset_event = controller.reset(scene=scene)
    target = _book(reset_event.metadata)
    if target is None or not target.get("objectId"):
        return {"passed": False, "reason": "pickupable_book_unavailable_after_reset"}
    poses = _sorted_interactable_poses(controller, str(target["objectId"]))
    trials: list[dict[str, Any]] = []
    for pose_order, pose in enumerate(poses[:max_pose_trials], start=1):
        trial_reset = controller.reset(scene=scene)
        trial_target = _book(trial_reset.metadata)
        if trial_target is None or not trial_target.get("objectId"):
            return {"passed": False, "reason": "book_unavailable_after_trial_reset"}
        object_id = str(trial_target["objectId"])
        teleport = controller.step(action="TeleportFull", **pose)
        teleport_success = teleport.metadata.get("lastActionSuccess") is True
        visible = teleport_success and _visible(teleport.metadata, object_id)
        pickup_success = False
        pickup_error = ""
        if visible:
            pickup = controller.step(action="PickupObject", objectId=object_id)
            pickup_success = pickup.metadata.get("lastActionSuccess") is True
            pickup_error = str(pickup.metadata.get("errorMessage", ""))
        trial = {
            "pose_order": pose_order,
            "pose": pose,
            "pose_digest": _digest(pose),
            "teleport_success": teleport_success,
            "visible_after_teleport": visible,
            "pickup_success": pickup_success,
            "teleport_error": str(teleport.metadata.get("errorMessage", "")),
            "pickup_error": pickup_error,
        }
        trials.append(trial)
        if pickup_success:
            return {
                "passed": True,
                "reason": "",
                "interactable_pose_count": len(poses),
                "selected_pose": pose,
                "selected_pose_order": pose_order,
                "selected_pose_digest": trial["pose_digest"],
                "target_object_id": object_id,
                "pose_trials": trials,
            }
    return {
        "passed": False,
        "reason": "no_visible_and_pickupable_pose_within_frozen_trial_limit",
        "interactable_pose_count": len(poses),
        "pose_trials": trials,
    }


def _check_route(controller: Any, *, scene: str, pose: Mapping[str, Any]) -> dict[str, Any]:
    controller.reset(scene=scene)
    reachable_event = controller.step(action="GetReachablePositions")
    if reachable_event.metadata.get("lastActionSuccess") is not True:
        return {
            "passed": False,
            "reason": "get_reachable_positions_failed",
            "error": str(reachable_event.metadata.get("errorMessage", "")),
        }
    reachable = reachable_event.metadata.get("actionReturn") or []
    route = build_target_independent_coverage_route(
        reachable_positions=reachable,
        start_position=pose,
        start_yaw=float(pose["rotation"]),
        grid_size=float(CONTROLLER_SETTINGS["gridSize"]),
    )
    action_count = len(route["actions"])
    passed = action_count <= ROUTE_ACTION_LIMIT
    return {
        "passed": passed,
        "reason": "" if passed else "route_exceeds_frozen_action_limit",
        "action_limit": ROUTE_ACTION_LIMIT,
        "action_count": action_count,
        "reachable_node_count": route["reachable_node_count"],
        "scan_waypoint_count": route["scan_waypoint_count"],
        "complete_graph_coverage": route["complete_graph_coverage"],
        "all_nodes_within_nominal_scan_radius": route[
            "all_nodes_within_nominal_scan_radius"
        ],
        "route_digest": stable_digest(route),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-pose-trials", type=int, default=32)
    args = parser.parse_args()
    if args.max_pose_trials < 1:
        raise ValueError("max-pose-trials must be positive")

    census = json.loads(args.census.resolve().read_text(encoding="utf-8"))
    all_presence_scenes = _ordered_presence_scenes(census)
    scenes = all_presence_scenes[INITIAL_BATCH_SIZE:]
    if len(scenes) != 29:
        raise ValueError("remaining candidate batch must contain exactly 29 scenes")

    from ai2thor.controller import Controller

    controller = Controller(scene=scenes[0], **CONTROLLER_SETTINGS)
    rows: list[dict[str, Any]] = []
    runtime_error_count = 0
    try:
        for presence_order, scene in enumerate(
            scenes, start=INITIAL_BATCH_SIZE + 1
        ):
            row: dict[str, Any] = {
                "presence_order": presence_order,
                "scene": scene,
                "runtime_error": "",
            }
            try:
                start = _qualify_start(
                    controller,
                    scene=scene,
                    max_pose_trials=args.max_pose_trials,
                )
                row["start_qualification"] = start
                if start["passed"]:
                    row["route_qualification"] = _check_route(
                        controller, scene=scene, pose=start["selected_pose"]
                    )
                else:
                    row["route_qualification"] = {
                        "passed": False,
                        "reason": "skipped_after_start_rejection",
                    }
            except Exception as exc:
                runtime_error_count += 1
                row["runtime_error"] = f"{type(exc).__name__}: {exc}"
                row.setdefault(
                    "start_qualification",
                    {"passed": False, "reason": "runtime_error"},
                )
                row.setdefault(
                    "route_qualification",
                    {"passed": False, "reason": "runtime_error"},
                )
            row["prescreen_passed"] = bool(
                row["start_qualification"]["passed"]
                and row["route_qualification"]["passed"]
                and not row["runtime_error"]
            )
            rows.append(row)
            print(
                json.dumps(
                    {
                        "presence_order": presence_order,
                        "scene": scene,
                        "start_passed": row["start_qualification"]["passed"],
                        "interactable_pose_count": row["start_qualification"].get(
                            "interactable_pose_count", 0
                        ),
                        "selected_pose_order": row["start_qualification"].get(
                            "selected_pose_order"
                        ),
                        "selected_pose_digest": row["start_qualification"].get(
                            "selected_pose_digest"
                        ),
                        "route_passed": row["route_qualification"]["passed"],
                        "route_action_count": row["route_qualification"].get(
                            "action_count"
                        ),
                        "route_digest": row["route_qualification"].get("route_digest"),
                        "runtime_error": row["runtime_error"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    finally:
        controller.stop()

    eligible = [row["scene"] for row in rows if row["prescreen_passed"]]
    result = {
        "prescreen_version": SCRIPT_VERSION,
        "boundary": BOUNDARY,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": "remaining-candidate start and route QA; not anchor, task, or memory qualification",
        "source_census_digest": _digest(census),
        "runtime": {
            "ai2thor_version": _package_version("ai2thor"),
            **_git_state(),
        },
        "controller_settings": CONTROLLER_SETTINGS,
        "selection_rule": "all presence candidates after positions 1-6, preserving frozen declared order",
        "initial_batch_size": INITIAL_BATCH_SIZE,
        "remaining_candidate_count": len(scenes),
        "route_action_limit": ROUTE_ACTION_LIMIT,
        "max_pose_trials_per_scene": args.max_pose_trials,
        "images_saved": False,
        "memory_agents_run": False,
        "runtime_error_count": runtime_error_count,
        "start_qualified_count": sum(
            row["start_qualification"]["passed"] for row in rows
        ),
        "remaining_route_eligible_count": len(eligible),
        "remaining_route_eligible_scenes_in_declared_order": eligible,
        "combined_route_eligible_count_including_initial_floorplan202": len(eligible) + 1,
        "six_route_eligible_pool_feasible": len(eligible) + 1 >= 6,
        "rows": rows,
    }
    _write_json(args.output.resolve(), result)
    print(
        "SUMMARY "
        + json.dumps(
            {
                "remaining_candidate_count": len(scenes),
                "runtime_error_count": runtime_error_count,
                "start_qualified_count": result["start_qualified_count"],
                "remaining_route_eligible_count": len(eligible),
                "combined_route_eligible_count": len(eligible) + 1,
                "six_route_eligible_pool_feasible": result[
                    "six_route_eligible_pool_feasible"
                ],
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if runtime_error_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

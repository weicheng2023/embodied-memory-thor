#!/usr/bin/env python3
"""Qualify one real ordered Cup/CoffeeMachine configuration without memory agents."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.phase4.contracts import (  # noqa: E402
    PlannerRequest,
    audit_planner_request,
    build_planner_observation,
)
from embodied_memory_thor.phase4.planners import (  # noqa: E402
    THOR_CUP_COFFEE_ACTIONS,
    ThorBookReacquirePlanner,
    validate_planner_decision,
)
from embodied_memory_thor.phase5.anchors import (  # noqa: E402
    build_target_independent_coverage_route,
    stable_digest,
)
from embodied_memory_thor.phase5.r2 import (  # noqa: E402
    R2_QUALIFICATION_VERSION,
    build_task_subgoal_route,
    normalize_interactable_pose,
    pose_sort_key,
    route_action_codes,
)
from embodied_memory_thor.phase5.search import (  # noqa: E402
    FrozenSearchRoute,
)
from embodied_memory_thor.phase5.target_lock import (  # noqa: E402
    SharedTargetLockPolicy,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


BOUNDARY = "EVALUATOR-ONLY R2 QUALIFICATION - NEVER PLANNER INPUT"
SCRIPT_VERSION = "phase5-r2-qualification-batch-v1"
CONTROLLER_SETTINGS = {
    "width": 300,
    "height": 300,
    "quality": "Low",
    "gridSize": 0.25,
    "snapToGrid": True,
    "rotateStepDegrees": 90,
    "fieldOfView": 90,
    "renderDepthImage": False,
    "renderInstanceSegmentation": False,
}
MAX_CANDIDATE_PAIRS = 12
MAX_SUBGOAL_ACTIONS = 240
MAX_FALLBACK_ACTIONS = 240
MAX_TARGET_LOCK_ACTIONS = 32
K_SHORT_MEMORY = 2


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _git_state() -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return {"code_revision": revision, "working_tree_dirty": dirty}


def _objects(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = metadata.get("objects", [])
    return (
        [item for item in raw if isinstance(item, Mapping)]
        if isinstance(raw, list)
        else []
    )


def _object(
    metadata: Mapping[str, Any], object_id: str
) -> Mapping[str, Any] | None:
    return next(
        (
            item
            for item in _objects(metadata)
            if str(item.get("objectId", "")) == object_id
        ),
        None,
    )


def _visible(metadata: Mapping[str, Any], object_id: str) -> bool:
    item = _object(metadata, object_id)
    return bool(item and item.get("visible") is True)


def _picked(metadata: Mapping[str, Any], object_id: str) -> bool:
    inventory = metadata.get("inventoryObjects", [])
    return bool(
        isinstance(inventory, list)
        and any(
            isinstance(item, Mapping)
            and str(item.get("objectId", "")) == object_id
            for item in inventory
        )
    )


def _toggled(metadata: Mapping[str, Any], object_id: str) -> bool:
    item = _object(metadata, object_id)
    return bool(item and item.get("isToggled") is True)


def _first_target(
    metadata: Mapping[str, Any], *, object_type: str, predicate: str
) -> Mapping[str, Any]:
    matches = sorted(
        (
            item
            for item in _objects(metadata)
            if item.get("objectType") == object_type
            and item.get(predicate) is True
            and item.get("objectId")
        ),
        key=lambda item: str(item["objectId"]),
    )
    if not matches:
        raise RuntimeError(f"no {predicate} {object_type} exists after reset")
    return matches[0]


def _reset(env: ThorEnv, scene: str) -> Mapping[str, Any]:
    env.reset(scene)
    return env.get_evaluator_state()


def _query_poses(
    env: ThorEnv, *, scene: str, object_id: str
) -> list[dict[str, Any]]:
    _reset(env, scene)
    event = env.step({"action": "GetInteractablePoses", "objectId": object_id})
    if event.metadata.get("lastActionSuccess") is not True:
        raise RuntimeError(
            "GetInteractablePoses failed: "
            + str(event.metadata.get("errorMessage", ""))
        )
    raw = event.metadata.get("actionReturn") or []
    poses = sorted(
        (
            pose
            for pose in (
                normalize_interactable_pose(item)
                for item in raw
                if isinstance(item, Mapping)
            )
            if pose is not None and pose["standing"] is True
        ),
        key=pose_sort_key,
    )
    if not poses:
        raise RuntimeError("no standing interactable pose was returned")
    return poses


def _reachable(env: ThorEnv, *, scene: str) -> list[dict[str, Any]]:
    _reset(env, scene)
    event = env.step({"action": "GetReachablePositions"})
    raw = event.metadata.get("actionReturn") or []
    points = [dict(item) for item in raw if isinstance(item, Mapping)]
    if event.metadata.get("lastActionSuccess") is not True or not points:
        raise RuntimeError("GetReachablePositions failed")
    return points


def _candidate_pairs(
    cup_poses: Sequence[Mapping[str, Any]],
    machine_poses: Sequence[Mapping[str, Any]],
) -> list[tuple[int, int, Mapping[str, Any], Mapping[str, Any]]]:
    pairs = [
        (cup_index, machine_index, cup_pose, machine_pose)
        for cup_index, cup_pose in enumerate(cup_poses, start=1)
        for machine_index, machine_pose in enumerate(machine_poses, start=1)
    ]
    return sorted(
        pairs,
        key=lambda row: (max(row[0], row[1]), row[0] + row[1], row[0], row[1]),
    )[:MAX_CANDIDATE_PAIRS]


def _actions(route: Mapping[str, Any]) -> list[dict[str, str]]:
    raw = route.get("actions", [])
    if not isinstance(raw, list):
        raise ValueError("route actions must be a list")
    result: list[dict[str, str]] = []
    for row in raw:
        action = row.get("action") if isinstance(row, Mapping) else None
        if not isinstance(action, Mapping) or set(action) != {"action"}:
            raise ValueError("route must contain navigation-only actions")
        result.append({"action": str(action["action"])})
    return result


def _route_replay(
    env: ThorEnv,
    *,
    route: Mapping[str, Any],
    cup_id: str,
) -> dict[str, Any]:
    action_log: list[dict[str, Any]] = []
    hidden_run = 0
    maximum_hidden_run = 0
    for index, action in enumerate(_actions(route), start=1):
        event = env.step(action)
        success = bool(event.metadata.get("lastActionSuccess", False))
        cup_visible = _visible(event.metadata, cup_id)
        hidden_run = 0 if cup_visible else hidden_run + 1
        maximum_hidden_run = max(maximum_hidden_run, hidden_run)
        action_log.append(
            {
                "index": index,
                "action": action,
                "success": success,
                "error": str(event.metadata.get("errorMessage", "")),
                "cup_visible_after": cup_visible,
                "continuous_cup_hidden_observations": hidden_run,
            }
        )
        if not success:
            return {
                "passed": False,
                "reason": "subgoal_route_action_failed",
                "action_log": action_log,
                "maximum_continuous_cup_hidden_observations": maximum_hidden_run,
                "continuous_cup_hidden_observations_at_route_end": hidden_run,
            }
    return {
        "passed": True,
        "reason": "",
        "action_log": action_log,
        "maximum_continuous_cup_hidden_observations": maximum_hidden_run,
        "continuous_cup_hidden_observations_at_route_end": hidden_run,
        "cup_hidden_at_route_end": not _visible(env.get_evaluator_state(), cup_id),
    }


def _fallback_pickup(
    env: ThorEnv,
    *,
    route: Mapping[str, Any],
    cup_id: str,
) -> dict[str, Any]:
    route_actions = _actions(route)
    route_cursor = 0
    action_log: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []
    target_lock = SharedTargetLockPolicy(target_type="Cup")
    target_lock_action_count = 0
    discovery_step: int | None = None
    planner = ThorBookReacquirePlanner()
    while len(action_log) < MAX_FALLBACK_ACTIONS + MAX_TARGET_LOCK_ACTIONS:
        observation = build_planner_observation(env.get_observation())
        directive = target_lock.next_directive(
            observation,
            allowed_actions=THOR_CUP_COFFEE_ACTIONS,
        )
        if directive is not None:
            if discovery_step is None:
                discovery_step = len(action_log) + 1
            target_lock_action_count += 1
            if target_lock_action_count > MAX_TARGET_LOCK_ACTIONS:
                return {
                    "passed": False,
                    "reason": "target_lock_total_action_limit_exceeded",
                    "action_log": action_log,
                    **target_lock.snapshot(),
                }
            request = PlannerRequest(
                task_name="thor_cup_after_coffee_subgoal",
                instruction="After the CoffeeMachine subgoal, reacquire and pick up Cup.",
                task_stage="pickup_cup",
                step=len(action_log) + 1,
                max_steps=MAX_FALLBACK_ACTIONS + MAX_TARGET_LOCK_ACTIONS,
                observation=observation,
                allowed_actions=THOR_CUP_COFFEE_ACTIONS,
                retrieved_memory=(),
                recent_action_results=tuple(deepcopy(recent[-5:])),
                target_lock=directive,
            )
            audit = audit_planner_request(request)
            decision = planner.plan(request)
            valid, errors = validate_planner_decision(decision, request)
            if not audit.passed or not valid:
                return {
                    "passed": False,
                    "reason": "target_lock_contract_failed:"
                    + ";".join((*audit.violations, *errors)),
                    "action_log": action_log,
                    **target_lock.snapshot(),
                }
            event = env.step(decision.action)
            success = bool(event.metadata.get("lastActionSuccess", False))
            post = build_planner_observation(env.get_observation())
            target_lock.record_result(
                directive,
                success=success,
                error_message=str(event.metadata.get("errorMessage", "")),
                observation_after=post,
                allowed_actions=THOR_CUP_COFFEE_ACTIONS,
            )
            row = {
                "index": len(action_log) + 1,
                "source": "planner_safe_target_lock",
                "action": dict(decision.action),
                "success": success,
                "error": str(event.metadata.get("errorMessage", "")),
            }
            action_log.append(row)
            recent.append(row)
            if _picked(event.metadata, cup_id):
                return {
                    "passed": True,
                    "reason": "",
                    "discovery_step": discovery_step,
                    "pickup_step": len(action_log),
                    "coverage_actions_consumed": route_cursor,
                    "action_log": action_log,
                    **target_lock.snapshot(),
                }
            if target_lock.metrics.target_lock_failed_reason and not target_lock.active:
                return {
                    "passed": False,
                    "reason": "target_lock_failed:"
                    + target_lock.metrics.target_lock_failed_reason,
                    "action_log": action_log,
                    **target_lock.snapshot(),
                }
            continue
        if route_cursor >= len(route_actions):
            return {
                "passed": False,
                "reason": "target_not_rediscovered_before_fallback_exhaustion",
                "discovery_step": discovery_step,
                "action_log": action_log,
                **target_lock.snapshot(),
            }
        action = route_actions[route_cursor]
        route_cursor += 1
        event = env.step(action)
        success = bool(event.metadata.get("lastActionSuccess", False))
        row = {
            "index": len(action_log) + 1,
            "source": "target_independent_fallback",
            "route_action_index": route_cursor - 1,
            "action": action,
            "success": success,
            "error": str(event.metadata.get("errorMessage", "")),
        }
        action_log.append(row)
        recent.append(row)
        if not success:
            return {
                "passed": False,
                "reason": "fallback_route_action_failed",
                "discovery_step": discovery_step,
                "action_log": action_log,
                **target_lock.snapshot(),
            }
    return {
        "passed": False,
        "reason": "fallback_total_action_limit_exceeded",
        "action_log": action_log,
        **target_lock.snapshot(),
    }


def _trial(
    env: ThorEnv,
    *,
    scene: str,
    cup_id: str,
    machine_id: str,
    start_pose: Mapping[str, Any],
    subgoal_route: Mapping[str, Any],
    fallback_route: Mapping[str, Any],
) -> dict[str, Any]:
    _reset(env, scene)
    teleport = env.step({"action": "TeleportFull", **dict(start_pose)})
    metadata = teleport.metadata
    cup = _object(metadata, cup_id)
    machine = _object(metadata, machine_id)
    preconditions = {
        "teleport_success": metadata.get("lastActionSuccess") is True,
        "cup_exists": cup is not None,
        "cup_visible": bool(cup and cup.get("visible") is True),
        "cup_pickupable": bool(cup and cup.get("pickupable") is True),
        "coffee_machine_exists": machine is not None,
        "coffee_machine_initially_off": bool(
            machine and machine.get("isToggled") is not True
        ),
        "coffee_machine_initially_hidden": bool(
            machine and machine.get("visible") is not True
        ),
    }
    if not all(preconditions.values()):
        return {
            "passed": False,
            "reason": "start_precondition_failed",
            "preconditions": preconditions,
        }
    replay = _route_replay(env, route=subgoal_route, cup_id=cup_id)
    if not replay["passed"]:
        return {
            "passed": False,
            "reason": replay["reason"],
            "preconditions": preconditions,
            "subgoal_route_replay": replay,
        }
    at_subgoal = env.get_evaluator_state()
    subgoal_postconditions = {
        "coffee_machine_visible": _visible(at_subgoal, machine_id),
        "cup_hidden": not _visible(at_subgoal, cup_id),
        "k2_evicted_before_toggle": (
            replay["continuous_cup_hidden_observations_at_route_end"]
            >= K_SHORT_MEMORY
        ),
    }
    if not all(subgoal_postconditions.values()):
        return {
            "passed": False,
            "reason": "subgoal_route_postcondition_failed",
            "preconditions": preconditions,
            "subgoal_route_replay": replay,
            "subgoal_postconditions": subgoal_postconditions,
        }
    toggle = env.step({"action": "ToggleObjectOn", "objectId": machine_id})
    toggle_record = {
        "success": toggle.metadata.get("lastActionSuccess") is True,
        "error": str(toggle.metadata.get("errorMessage", "")),
        "coffee_machine_toggled": _toggled(toggle.metadata, machine_id),
        "cup_hidden_after_toggle": not _visible(toggle.metadata, cup_id),
    }
    if not (
        toggle_record["success"]
        and toggle_record["coffee_machine_toggled"]
        and toggle_record["cup_hidden_after_toggle"]
    ):
        return {
            "passed": False,
            "reason": "coffee_machine_toggle_failed",
            "preconditions": preconditions,
            "subgoal_route_replay": replay,
            "subgoal_postconditions": subgoal_postconditions,
            "toggle": toggle_record,
        }
    fallback = _fallback_pickup(env, route=fallback_route, cup_id=cup_id)
    return {
        "passed": bool(fallback["passed"]),
        "reason": "" if fallback["passed"] else fallback["reason"],
        "preconditions": preconditions,
        "subgoal_route_replay": replay,
        "subgoal_postconditions": subgoal_postconditions,
        "toggle": toggle_record,
        "fallback": fallback,
    }


def _restoration(
    env: ThorEnv,
    *,
    scene: str,
    cup_id: str,
    machine_id: str,
    start_pose: Mapping[str, Any],
) -> dict[str, Any]:
    _reset(env, scene)
    event = env.step({"action": "TeleportFull", **dict(start_pose)})
    passed = bool(
        event.metadata.get("lastActionSuccess") is True
        and _visible(event.metadata, cup_id)
        and not _toggled(event.metadata, machine_id)
        and not _picked(event.metadata, cup_id)
    )
    return {
        "passed": passed,
        "teleport_success": event.metadata.get("lastActionSuccess") is True,
        "cup_visible": _visible(event.metadata, cup_id),
        "coffee_machine_off": not _toggled(event.metadata, machine_id),
        "cup_not_in_inventory": not _picked(event.metadata, cup_id),
    }


def _public_route(
    *,
    route_id: str,
    scene: str,
    source_digest: str,
    route: Mapping[str, Any],
    route_role: str,
) -> dict[str, Any]:
    action_codes = route_action_codes(route)
    actions = _actions(route)
    frozen = FrozenSearchRoute(
        route_id=route_id,
        task="thor_cup_after_coffee_subgoal",
        scene=scene,
        source_qualification_route_digest=source_digest,
        action_sequence_digest=stable_digest(actions),
        action_codes=action_codes,
        route_role=route_role,
        qualification_goal_input_used=route_role == "task_subgoal_navigation",
        target_or_anchor_input_used=route_role == "task_subgoal_navigation",
    )
    frozen.validate()
    return {
        **frozen.public_reference(),
        "action_codes": action_codes,
        "entry_position_tolerance_meters": frozen.entry_position_tolerance_meters,
        "entry_angle_tolerance_degrees": frozen.entry_angle_tolerance_degrees,
    }


def _public_summary(
    *,
    scene: str,
    git_state: Mapping[str, Any],
    output_dir: Path,
    candidate_count: int,
    trial_records: Sequence[Mapping[str, Any]],
    selected: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "qualification_version": R2_QUALIFICATION_VERSION,
        "script_version": SCRIPT_VERSION,
        "claim_boundary": (
            "single-scene evaluator qualification; no memory variant and no formal result"
        ),
        "scene": scene,
        "candidate_pair_policy": (
            "first-12 lexicographic rank-balanced pairs frozen before outcomes"
        ),
        "candidate_pair_limit": MAX_CANDIDATE_PAIRS,
        "candidate_pair_count": candidate_count,
        "candidate_trials_run": len(trial_records),
        "passed": selected is not None,
        "selected_candidate_order": (
            int(selected["candidate_order"]) if selected is not None else None
        ),
        "configuration_id": (
            str(selected["configuration_id"]) if selected is not None else None
        ),
        "start_pose_digest": (
            str(selected["start_pose_digest"]) if selected is not None else None
        ),
        "subgoal_route_id": (
            str(selected["subgoal_route"]["route_id"])
            if selected is not None
            else None
        ),
        "subgoal_route_action_count": (
            int(selected["subgoal_route"]["action_count"])
            if selected is not None
            else None
        ),
        "subgoal_route_qualification_goal_input_used": (
            True if selected is not None else None
        ),
        "fallback_route_id": (
            str(selected["fallback_route"]["route_id"])
            if selected is not None
            else None
        ),
        "fallback_route_action_count": (
            int(selected["fallback_route"]["action_count"])
            if selected is not None
            else None
        ),
        "fallback_target_or_anchor_input_used": (
            False if selected is not None else None
        ),
        "k2_eviction_gate_passed": (
            bool(selected["first_trial"]["subgoal_postconditions"]["k2_evicted_before_toggle"])
            if selected is not None
            else None
        ),
        "fresh_reset_replay_passed": (
            bool(selected["fresh_reset_replay"]["passed"])
            if selected is not None
            else None
        ),
        "reset_restoration_passed": (
            bool(selected["reset_restoration"]["passed"])
            if selected is not None
            else None
        ),
        "memory_agents_run": False,
        "images_saved": False,
        "coordinates_exposed_in_summary": False,
        "formal_use_allowed": False,
        "next_gate": (
            "freeze one public/private R2 runtime and run one excluded integration probe"
            if selected is not None
            else "inspect retained candidate failures before any later scene"
        ),
        "output_dir": str(output_dir),
        **dict(git_state),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="FloorPlan1")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.scene != "FloorPlan1":
        raise ValueError("the first R2 qualification run is frozen to FloorPlan1")
    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir is not None
        else PROJECT_ROOT / "outputs" / "phase5_r2_qualification" / _slug()
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    git_state = _git_state()
    if git_state["working_tree_dirty"]:
        summary = {
            "passed": False,
            "failure_reason": "clean_worktree_required",
            "output_dir": str(output_dir),
            **git_state,
        }
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 2

    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    candidate_plan: dict[str, Any] = {}
    trials: list[dict[str, Any]] = []
    selected_private: dict[str, Any] | None = None
    selected_public: dict[str, Any] | None = None
    fatal_error = ""
    try:
        metadata = _reset(env, args.scene)
        cup = _first_target(metadata, object_type="Cup", predicate="pickupable")
        machine = _first_target(
            metadata, object_type="CoffeeMachine", predicate="toggleable"
        )
        cup_id = str(cup["objectId"])
        machine_id = str(machine["objectId"])
        if machine.get("isToggled") is True:
            raise RuntimeError("deterministically selected CoffeeMachine starts toggled")
        cup_poses = _query_poses(env, scene=args.scene, object_id=cup_id)
        machine_poses = _query_poses(env, scene=args.scene, object_id=machine_id)
        reachable = _reachable(env, scene=args.scene)
        pairs = _candidate_pairs(cup_poses, machine_poses)
        precommitted: list[dict[str, Any]] = []
        for order, (cup_order, machine_order, start, destination) in enumerate(
            pairs, start=1
        ):
            row: dict[str, Any] = {
                "candidate_order": order,
                "cup_pose_order": cup_order,
                "coffee_machine_pose_order": machine_order,
                "start_pose": dict(start),
                "destination_pose": dict(destination),
                "start_pose_digest": stable_digest(start),
                "destination_pose_digest": stable_digest(destination),
                "prebuild_passed": False,
                "prebuild_error": "",
            }
            try:
                subgoal_route = build_task_subgoal_route(
                    reachable_positions=reachable,
                    start_pose=start,
                    destination_pose=destination,
                    grid_size=float(CONTROLLER_SETTINGS["gridSize"]),
                )
                fallback_route = build_target_independent_coverage_route(
                    reachable_positions=reachable,
                    start_position=destination,
                    start_yaw=float(destination["rotation"]),
                    grid_size=float(CONTROLLER_SETTINGS["gridSize"]),
                    start_camera_horizon_degrees=float(destination["horizon"]),
                    absolute_scan_horizon_degrees=0.0,
                )
                subgoal_count = len(_actions(subgoal_route))
                fallback_count = len(_actions(fallback_route))
                if subgoal_count > MAX_SUBGOAL_ACTIONS:
                    raise ValueError("subgoal_route_action_limit_exceeded")
                if fallback_count > MAX_FALLBACK_ACTIONS:
                    raise ValueError("fallback_route_action_limit_exceeded")
                row.update(
                    {
                        "prebuild_passed": True,
                        "subgoal_route": subgoal_route,
                        "subgoal_route_digest": stable_digest(subgoal_route),
                        "subgoal_route_action_count": subgoal_count,
                        "fallback_route": fallback_route,
                        "fallback_route_digest": stable_digest(fallback_route),
                        "fallback_route_action_count": fallback_count,
                    }
                )
            except Exception as exc:
                row["prebuild_error"] = f"{type(exc).__name__}: {exc}"
            precommitted.append(row)
        candidate_plan = {
            "qualification_version": R2_QUALIFICATION_VERSION,
            "script_version": SCRIPT_VERSION,
            "boundary": BOUNDARY,
            "created_at": _utc_now(),
            "created_before_native_trials": True,
            "selection_uses_trial_outcomes": False,
            "selection_rule": "first fully qualified pair in precommitted order",
            "scene": args.scene,
            "cup_object_id": cup_id,
            "coffee_machine_object_id": machine_id,
            "cup_interactable_pose_count": len(cup_poses),
            "coffee_machine_interactable_pose_count": len(machine_poses),
            "reachable_position_count": len(reachable),
            "candidate_pair_limit": MAX_CANDIDATE_PAIRS,
            "candidate_pairs": precommitted,
            **git_state,
        }
        candidate_plan["candidate_plan_digest"] = stable_digest(candidate_plan)
        _write_json(output_dir / "evaluator_only_candidate_plan.json", candidate_plan)

        for raw in precommitted:
            trial_row: dict[str, Any] = {
                "candidate_order": raw["candidate_order"],
                "prebuild_passed": raw["prebuild_passed"],
                "prebuild_error": raw["prebuild_error"],
            }
            if not raw["prebuild_passed"]:
                trial_row.update(
                    {"passed": False, "reason": "candidate_prebuild_failed"}
                )
                trials.append(trial_row)
                continue
            first = _trial(
                env,
                scene=args.scene,
                cup_id=cup_id,
                machine_id=machine_id,
                start_pose=raw["start_pose"],
                subgoal_route=raw["subgoal_route"],
                fallback_route=raw["fallback_route"],
            )
            trial_row["first_trial"] = first
            if first["passed"]:
                replay = _trial(
                    env,
                    scene=args.scene,
                    cup_id=cup_id,
                    machine_id=machine_id,
                    start_pose=raw["start_pose"],
                    subgoal_route=raw["subgoal_route"],
                    fallback_route=raw["fallback_route"],
                )
            else:
                replay = {
                    "passed": False,
                    "reason": "skipped_after_first_trial_failure",
                }
            trial_row["fresh_reset_replay"] = replay
            restoration = _restoration(
                env,
                scene=args.scene,
                cup_id=cup_id,
                machine_id=machine_id,
                start_pose=raw["start_pose"],
            )
            trial_row["reset_restoration"] = restoration
            passed = bool(first["passed"] and replay["passed"] and restoration["passed"])
            trial_row["passed"] = passed
            trial_row["reason"] = (
                ""
                if passed
                else first.get("reason")
                or replay.get("reason")
                or "reset_restoration_failed"
            )
            trials.append(trial_row)
            print(
                json.dumps(
                    {
                        "candidate_order": raw["candidate_order"],
                        "passed": passed,
                        "reason": trial_row["reason"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if passed:
                configuration_id = f"{args.scene}_R2_fixed_start_001"
                source_digest = stable_digest(
                    {
                        "candidate_plan_digest": candidate_plan[
                            "candidate_plan_digest"
                        ],
                        "candidate_order": raw["candidate_order"],
                        "first_trial": first,
                        "fresh_reset_replay": replay,
                        "reset_restoration": restoration,
                    }
                )
                subgoal_public = _public_route(
                    route_id=f"{configuration_id}_subgoal_v1",
                    scene=args.scene,
                    source_digest=source_digest,
                    route=raw["subgoal_route"],
                    route_role="task_subgoal_navigation",
                )
                fallback_public = _public_route(
                    route_id=f"{configuration_id}_fallback_absolute_v4",
                    scene=args.scene,
                    source_digest=source_digest,
                    route=raw["fallback_route"],
                    route_role="target_independent_fallback",
                )
                selected_private = {
                    "boundary": BOUNDARY,
                    "planner_visible": False,
                    "included_in_planner_metrics": False,
                    "configuration_id": configuration_id,
                    "scene": args.scene,
                    "target_cup_object_id": cup_id,
                    "coffee_machine_object_id": machine_id,
                    "start_action": {
                        "action": "TeleportFull",
                        **dict(raw["start_pose"]),
                    },
                    "destination_pose": dict(raw["destination_pose"]),
                    "start_pose_digest": raw["start_pose_digest"],
                    "destination_pose_digest": raw["destination_pose_digest"],
                    "source_qualification_digest": source_digest,
                    "candidate_order": raw["candidate_order"],
                    "first_trial": first,
                    "fresh_reset_replay": replay,
                    "reset_restoration": restoration,
                    "subgoal_route_private": raw["subgoal_route"],
                    "fallback_route_private": raw["fallback_route"],
                }
                selected_public = {
                    "qualification_version": R2_QUALIFICATION_VERSION,
                    "configuration_id": configuration_id,
                    "scene": args.scene,
                    "start_pose_digest": raw["start_pose_digest"],
                    "source_qualification_digest": source_digest,
                    "subgoal_route": subgoal_public,
                    "fallback_route": fallback_public,
                    "planner_visible_coordinates": False,
                    "formal_use_allowed": False,
                }
                break
    except Exception as exc:
        fatal_error = f"{type(exc).__name__}: {exc}"
    finally:
        env.close()

    private_result = {
        "qualification_version": R2_QUALIFICATION_VERSION,
        "script_version": SCRIPT_VERSION,
        "boundary": BOUNDARY,
        "candidate_plan_digest": candidate_plan.get("candidate_plan_digest"),
        "trials": trials,
        "selected_configuration": selected_private,
        "fatal_error": fatal_error,
        **git_state,
    }
    _write_json(output_dir / "evaluator_only_qualification.json", private_result)
    if selected_public is not None:
        _write_json(output_dir / "public_qualified_configuration.json", selected_public)
    summary = _public_summary(
        scene=args.scene,
        git_state=git_state,
        output_dir=output_dir,
        candidate_count=len(candidate_plan.get("candidate_pairs", [])),
        trial_records=trials,
        selected=(
            {
                **selected_public,
                "candidate_order": selected_private["candidate_order"],
                "first_trial": selected_private["first_trial"],
                "fresh_reset_replay": selected_private["fresh_reset_replay"],
                "reset_restoration": selected_private["reset_restoration"],
            }
            if selected_public is not None and selected_private is not None
            else None
        ),
    )
    if fatal_error:
        summary["failure_reason"] = fatal_error
    elif selected_public is None:
        summary["failure_reason"] = "no_candidate_fully_qualified"
    else:
        summary["failure_reason"] = ""
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

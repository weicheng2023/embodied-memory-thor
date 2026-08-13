#!/usr/bin/env python3
"""Pair an original-scene route replay with one frozen placement replay."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SCRIPT_ROOT = PROJECT_ROOT / "scripts"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.phase5.qualification import (  # noqa: E402
    place_object_at_point_action,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402
from qualify_phase5_anchors import (  # noqa: E402
    CONTROLLER_SETTINGS,
    _load_candidate_contract,
    _reset_setup,
    _setup_actions_for_candidate,
    _target,
)


SCRIPT_VERSION = "phase5-route-mutation-diagnostic-v1"
BOUNDARY = "EVALUATOR-ONLY PAIRED DIAGNOSTIC - NEVER PLANNER INPUT"


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


def _object_state(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw = metadata.get("objects", [])
    for obj in raw if isinstance(raw, list) else []:
        if not isinstance(obj, Mapping):
            continue
        rows.append(
            {
                "object_id": str(obj.get("objectId", "")),
                "object_type": str(obj.get("objectType", "")),
                "position": deepcopy(obj.get("position")),
                "rotation": deepcopy(obj.get("rotation")),
                "is_moving": obj.get("isMoving"),
                "is_picked_up": obj.get("isPickedUp"),
                "parent_receptacles": sorted(
                    str(value) for value in (obj.get("parentReceptacles") or [])
                ),
            }
        )
    return sorted(rows, key=lambda row: row["object_id"])


def _blocker_type(metadata: Mapping[str, Any], error: str) -> str:
    raw = metadata.get("objects", [])
    matches = sorted(
        (
            (len(str(obj.get("objectId", ""))), str(obj.get("objectType", "")))
            for obj in raw if isinstance(raw, list) and isinstance(obj, Mapping)
            if str(obj.get("objectId", ""))
            and str(obj.get("objectId", "")) in error
        ),
        reverse=True,
    )
    return matches[0][1] if matches else ""


def replay_route(
    env: Any,
    route: Mapping[str, Any],
    *,
    probe_step: int,
) -> dict[str, Any]:
    actions = route.get("actions", [])
    if not isinstance(actions, list) or not (1 <= probe_step <= len(actions)):
        raise ValueError("probe step must be within the frozen route")
    action_log: list[dict[str, Any]] = []
    for step, row in enumerate(actions, start=1):
        if not isinstance(row, Mapping) or not isinstance(row.get("action"), Mapping):
            raise ValueError("frozen route contains an invalid action row")
        event = env.step(dict(row["action"]))
        success = bool(event.metadata.get("lastActionSuccess", False))
        error = str(event.metadata.get("errorMessage", ""))
        action_log.append(
            {
                "step": step,
                "action": dict(row["action"]),
                "route_phase": row.get("phase"),
                "success": success,
                "error": error,
                "blocker_object_type": _blocker_type(event.metadata, error),
            }
        )
        if not success:
            break
    failed = next((row for row in action_log if not row["success"]), None)
    step_109 = next((row for row in action_log if row["step"] == probe_step), None)
    return {
        "route_action_count": len(actions),
        "route_actions_attempted": len(action_log),
        "route_completed": len(action_log) == len(actions) and failed is None,
        "probe_step": probe_step,
        "probe_step_attempted": step_109 is not None,
        "probe_step_success": step_109.get("success") if step_109 else None,
        "first_failed_route_step": failed.get("step") if failed else None,
        "failed_action_name": (
            failed.get("action", {}).get("action") if failed else ""
        ),
        "failed_route_phase": failed.get("route_phase") if failed else "",
        "blocker_object_type": failed.get("blocker_object_type") if failed else "",
        "action_log": action_log,
    }


def classify_pair(
    baseline: Mapping[str, Any],
    placement: Mapping[str, Any],
    *,
    placement_success: bool,
) -> dict[str, Any]:
    if not placement_success:
        return {
            "classification": "diagnostic_invalid_placement_failed",
            "decision": "stop",
            "good_news": False,
        }
    baseline_passed = baseline.get("route_completed") is True
    placement_passed = placement.get("route_completed") is True
    if not baseline_passed:
        return {
            "classification": "original_route_intrinsically_blocked",
            "decision": "mark_floorplan304_route_failure_and_stop",
            "good_news": False,
        }
    if not placement_passed:
        return {
            "classification": "book_placement_induced_route_failure",
            "decision": "preregister_general_obstacle_recovery_and_stop",
            "good_news": False,
        }
    return {
        "classification": "prior_route_block_not_reproduced_in_paired_probe",
        "decision": "allow_floorplan304_candidate1_continuation_only",
        "good_news": True,
    }


def _run_condition(
    env: Any,
    *,
    scene: str,
    setup_actions: Sequence[Mapping[str, Any]],
    route: Mapping[str, Any],
    probe_step: int,
    condition: str,
    target_id: str,
    support_id: str,
    point: Mapping[str, Any],
) -> dict[str, Any]:
    metadata, setup = _reset_setup(env, scene, setup_actions)
    before_state = _object_state(metadata)
    intervention_log: list[dict[str, Any]] = []
    if condition == "baseline":
        intervention_actions = [{"action": "Pass"} for _ in range(4)]
    elif condition == "placement":
        intervention_actions = [
            place_object_at_point_action(target_id, point),
            *({"action": "Pass"} for _ in range(3)),
        ]
    else:
        raise ValueError(f"unsupported paired condition: {condition}")
    for index, action in enumerate(intervention_actions, start=1):
        event = env.step(action)
        intervention_log.append(
            {
                "index": index,
                "action": dict(action),
                "success": bool(event.metadata.get("lastActionSuccess", False)),
                "error": str(event.metadata.get("errorMessage", "")),
            }
        )
        if intervention_log[-1]["success"] is not True:
            break
    after_intervention = env.get_evaluator_state()
    intervention_valid = (
        len(intervention_log) == 4
        and all(row["success"] for row in intervention_log)
    )
    placement_success = (
        None
        if condition == "baseline"
        else (
            intervention_valid
            and _target(after_intervention, target_id) is not None
            and support_id
            in (_target(after_intervention, target_id).get("parentReceptacles") or [])
        )
    )
    route_result = (
        replay_route(env, route, probe_step=probe_step)
        if len(intervention_log) == 4 and all(row["success"] for row in intervention_log)
        else {
            "route_action_count": len(route.get("actions", [])),
            "route_actions_attempted": 0,
            "route_completed": False,
            "probe_step": probe_step,
            "probe_step_attempted": False,
            "probe_step_success": None,
            "first_failed_route_step": None,
            "failed_action_name": "",
            "failed_route_phase": "",
            "blocker_object_type": "",
            "action_log": [],
        }
    )
    final_state = _object_state(env.get_evaluator_state())
    return {
        "condition": condition,
        "setup": setup,
        "intervention_log": intervention_log,
        "intervention_valid": intervention_valid,
        "placement_success": placement_success,
        "before_state_digest": stable_digest(before_state),
        "after_intervention_state_digest": stable_digest(
            _object_state(after_intervention)
        ),
        "final_state_digest": stable_digest(final_state),
        "before_state": before_state,
        "after_intervention_state": _object_state(after_intervention),
        "final_state": final_state,
        "route": route_result,
    }


def _public_condition(record: Mapping[str, Any]) -> dict[str, Any]:
    route = record["route"]
    return {
        "condition": record["condition"],
        "intervention_action_count": len(record["intervention_log"]),
        "intervention_actions_succeeded": all(
            row["success"] for row in record["intervention_log"]
        ),
        "intervention_valid": record["intervention_valid"],
        "placement_success": record["placement_success"],
        "before_state_digest": record["before_state_digest"],
        "after_intervention_state_digest": record["after_intervention_state_digest"],
        "route_actions_attempted": route["route_actions_attempted"],
        "route_completed": route["route_completed"],
        "probe_step": route["probe_step"],
        "probe_step_attempted": route["probe_step_attempted"],
        "probe_step_success": route["probe_step_success"],
        "first_failed_route_step": route["first_failed_route_step"],
        "failed_action_name": route["failed_action_name"],
        "failed_route_phase": route["failed_route_phase"],
        "blocker_object_type": route["blocker_object_type"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--candidate-contract", type=Path, required=True)
    parser.add_argument("--start-registry", type=Path, action="append", required=True)
    parser.add_argument("--prior-candidate-plan", type=Path, required=True)
    parser.add_argument("--route-file", type=Path, required=True)
    parser.add_argument("--candidate-order", type=int, default=1)
    parser.add_argument("--probe-step", type=int, default=109)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    git_state = _git_state()
    if git_state["working_tree_dirty"]:
        summary = {"passed": False, "reason": "clean_worktree_required", **git_state}
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 2

    contract = _load_candidate_contract(args.candidate_contract.resolve(), args.scene)
    setup, configuration_id, _, route_digest, route_count, _, _ = (
        _setup_actions_for_candidate(
            scene=args.scene,
            candidate_contract=args.candidate_contract,
            start_registries=args.start_registry,
        )
    )
    plan = json.loads(args.prior_candidate_plan.resolve().read_text(encoding="utf-8"))
    route = json.loads(args.route_file.resolve().read_text(encoding="utf-8"))
    if plan.get("scene") != args.scene or plan.get("configuration_id") != configuration_id:
        raise ValueError("prior candidate plan does not match the frozen scene contract")
    if stable_digest(route) != route_digest or len(route.get("actions", [])) != route_count:
        raise ValueError("private route does not match the public digest/count contract")
    candidates = plan.get("geometry", {}).get("accepted_candidates", [])
    selected = [
        row for row in candidates
        if isinstance(row, Mapping) and row.get("candidate_order") == args.candidate_order
    ]
    if len(selected) != 1 or selected[0].get("support_type") != "Bed":
        raise ValueError("diagnostic requires frozen candidate 1 to be a Bed candidate")
    candidate = selected[0]
    target_id = str(plan["target"]["object_id"])

    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    try:
        baseline = _run_condition(
            env,
            scene=args.scene,
            setup_actions=setup,
            route=route,
            probe_step=args.probe_step,
            condition="baseline",
            target_id=target_id,
            support_id=str(candidate["support_id"]),
            point=candidate["point"],
        )
        placement = _run_condition(
            env,
            scene=args.scene,
            setup_actions=setup,
            route=route,
            probe_step=args.probe_step,
            condition="placement",
            target_id=target_id,
            support_id=str(candidate["support_id"]),
            point=candidate["point"],
        )
    finally:
        env.close()

    decision = classify_pair(
        baseline["route"],
        placement["route"],
        placement_success=bool(placement["placement_success"]),
    )
    private = {
        "diagnostic_version": SCRIPT_VERSION,
        "boundary": BOUNDARY,
        "scene": args.scene,
        "configuration_id": configuration_id,
        "candidate_order": args.candidate_order,
        "candidate_plan_digest": plan.get("candidate_plan_digest"),
        "route_digest": route_digest,
        "route_action_count": route_count,
        "probe_step": args.probe_step,
        "baseline": baseline,
        "placement": placement,
        **decision,
        **git_state,
    }
    private_digest = stable_digest(private)
    private["private_diagnostic_digest"] = private_digest
    _write_json(output_dir / "evaluator_only_paired_route_diagnostic.json", private)
    summary = {
        "diagnostic_version": SCRIPT_VERSION,
        "claim": "paired route-mutation isolation; not anchor qualification or memory comparison",
        "scene": args.scene,
        "configuration_id": configuration_id,
        "candidate_order": args.candidate_order,
        "route_digest": route_digest,
        "route_action_count": route_count,
        "probe_step": args.probe_step,
        "baseline": _public_condition(baseline),
        "placement": _public_condition(placement),
        **decision,
        "support_queries_run": False,
        "new_candidates_generated": False,
        "planner_run": False,
        "memory_agents_run": False,
        "images_saved": False,
        "obstacle_recovery_actions_run": False,
        "later_scenes_started": False,
        "coordinates_exposed": False,
        "private_diagnostic_digest": private_digest,
        **git_state,
    }
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

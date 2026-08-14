#!/usr/bin/env python3
"""Run one excluded FloorPlan5 exhaustive-visual-fallback diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.phase5.anchors import (  # noqa: E402
    VISUAL_FALLBACK_ACTION_LIMIT,
    VISUAL_FALLBACK_POLICY_VERSION,
    build_target_independent_visual_fallback_route,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


DIAGNOSTIC_VERSION = "phase5-r2-floorplan5-visual-fallback-v1"
BOUNDARY = "EVALUATOR-ONLY FLOORPLAN5 VISUAL FALLBACK DIAGNOSTIC - NEVER PLANNER INPUT"
DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "phase5_r2_floorplan5_visual_fallback_diagnostic_v1.json"
)
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


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _git_state() -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    return {"code_revision": revision, "working_tree_dirty": dirty}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _qualifier_module() -> Any:
    path = PROJECT_ROOT / "scripts" / "qualify_phase5_r2.py"
    spec = importlib.util.spec_from_file_location(
        "qualify_phase5_r2_for_visual_fallback", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load R2 qualifier module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _one_candidate(rows: Any, order: int) -> Mapping[str, Any]:
    matches = [
        row for row in rows
        if isinstance(row, Mapping) and int(row.get("candidate_order", -1)) == order
    ] if isinstance(rows, list) else []
    if len(matches) != 1:
        raise ValueError("expected exactly one frozen source candidate")
    return matches[0]


def validate_preconditions(
    config: Mapping[str, Any],
    plan: Mapping[str, Any],
    qualification: Mapping[str, Any],
) -> Mapping[str, Any]:
    if config.get("diagnostic_version") != DIAGNOSTIC_VERSION:
        raise ValueError("diagnostic version mismatch")
    if config.get("scene") != "FloorPlan5":
        raise ValueError("diagnostic scene mismatch")
    if config.get("visual_fallback_policy_version") != VISUAL_FALLBACK_POLICY_VERSION:
        raise ValueError("visual fallback policy mismatch")
    construction = config.get("route_construction", {})
    if not isinstance(construction, Mapping):
        raise ValueError("route construction contract missing")
    if int(construction.get("fallback_action_limit", -1)) != VISUAL_FALLBACK_ACTION_LIMIT:
        raise ValueError("visual fallback action limit mismatch")
    for forbidden_flag in (
        "target_or_anchor_input_used",
        "qualification_goal_input_used",
        "memory_variant_input_used",
    ):
        if construction.get(forbidden_flag) is not False:
            raise ValueError(f"forbidden route input enabled: {forbidden_flag}")
    if construction.get("route_built_once_and_shared_by_all_variants") is not True:
        raise ValueError("shared-variant route contract missing")
    if config.get("shared_variant_contract") != [
        "no_memory", "short_memory_k2", "object_memory"
    ]:
        raise ValueError("memory variant contract mismatch")
    for relative, expected in config.get("memory_provider_files_frozen", {}).items():
        if _sha256(PROJECT_ROOT / str(relative)) != str(expected):
            raise ValueError(f"memory provider changed: {relative}")
    for relative, expected in config.get("prior_evidence_files_frozen", {}).items():
        if _sha256(PROJECT_ROOT / str(relative)) != str(expected):
            raise ValueError(f"prior evidence changed: {relative}")
    if plan.get("candidate_plan_digest") != config.get("source_candidate_plan_digest"):
        raise ValueError("source candidate-plan digest mismatch")
    if qualification.get("code_revision") != config.get("source_revision"):
        raise ValueError("source qualification revision mismatch")
    order = int(config["candidate_order"])
    candidate = _one_candidate(plan.get("candidate_pairs"), order)
    expected = {
        "start_pose_digest": candidate.get("start_pose_digest"),
        "destination_pose_digest": candidate.get("destination_pose_digest"),
        "subgoal_route_digest": candidate.get("subgoal_route_digest"),
        "subgoal_action_count": candidate.get("subgoal_route_action_count"),
        "failed_fallback_route_digest": candidate.get("fallback_route_digest"),
        "failed_fallback_action_count": candidate.get("fallback_route_action_count"),
    }
    for key, actual in expected.items():
        if config.get(key) != actual:
            raise ValueError(f"source candidate contract mismatch: {key}")
    source_trial = _one_candidate(qualification.get("trials"), order)
    first = source_trial.get("first_trial", {})
    fallback = first.get("fallback", {}) if isinstance(first, Mapping) else {}
    actions = fallback.get("action_log", []) if isinstance(fallback, Mapping) else []
    if (
        source_trial.get("reason") != "target_not_rediscovered_before_fallback_exhaustion"
        or not isinstance(actions, list)
        or len(actions) != int(config["failed_fallback_action_count"])
        or any(
            not isinstance(row, Mapping) or row.get("success") is not True
            for row in actions
        )
    ):
        raise ValueError("source is not the frozen clean visual-coverage failure")
    return candidate


def build_public_summary(
    *,
    trial: Mapping[str, Any],
    restoration: Mapping[str, Any],
    route: Mapping[str, Any],
    git_state: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    fallback = trial.get("fallback", {}) if isinstance(trial, Mapping) else {}
    action_log = fallback.get("action_log", []) if isinstance(fallback, Mapping) else []
    preconditions = trial.get("preconditions", {}) if isinstance(trial, Mapping) else {}
    subgoal = trial.get("subgoal_route_replay", {}) if isinstance(trial, Mapping) else {}
    toggle = trial.get("toggle", {}) if isinstance(trial, Mapping) else {}
    action_failures = sum(
        1 for row in action_log
        if not isinstance(row, Mapping) or row.get("success") is not True
    ) if isinstance(action_log, list) else 0
    task_integrity = bool(
        isinstance(preconditions, Mapping)
        and preconditions
        and all(preconditions.values())
        and isinstance(subgoal, Mapping)
        and subgoal.get("passed") is True
        and isinstance(toggle, Mapping)
        and toggle.get("success") is True
        and action_failures == 0
    )
    passed = bool(task_integrity and trial.get("passed") is True and restoration.get("passed") is True)
    reason = str(trial.get("reason", ""))
    if passed:
        failure_classification = "resolved_visual_coverage_failure"
    elif (
        reason == "start_precondition_failed"
        and isinstance(preconditions, Mapping)
        and preconditions.get("cup_visible") is False
        and restoration.get("passed") is True
        and restoration.get("cup_visible") is True
    ):
        failure_classification = "frozen_start_visibility_nonreproduction"
    elif reason == "target_not_rediscovered_before_fallback_exhaustion":
        failure_classification = "visual_coverage_failure_persists"
    elif reason == "fallback_route_action_failed":
        failure_classification = "fallback_route_execution_failure"
    else:
        failure_classification = "diagnostic_integrity_or_interaction_failure"
    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "claim_boundary": "one excluded real FloorPlan5 fallback diagnostic; no memory variant and no formal result",
        "scene": "FloorPlan5",
        "candidate_order": 2,
        "source_failure_classification": "visual_coverage_failure",
        "visual_fallback_policy_version": route.get("route_version"),
        "visual_fallback_action_limit": route.get("action_limit"),
        "reachable_node_count": route.get("reachable_node_count"),
        "visited_node_count": route.get("visited_node_count"),
        "scan_node_count": route.get("scan_node_count"),
        "scan_horizons_degrees": route.get("scan_horizons_degrees"),
        "planned_route_action_count": len(route.get("actions", [])),
        "route_digest": route.get("route_digest"),
        "target_or_anchor_input_used": route.get("target_or_anchor_input_used"),
        "qualification_goal_input_used": route.get("qualification_goal_input_used"),
        "memory_variant_input_used": route.get("memory_variant_input_used"),
        "every_reachable_node_visited": route.get("every_reachable_node_visited"),
        "every_reachable_node_scanned_at_both_horizons": route.get(
            "every_reachable_node_scanned_at_both_horizons"
        ),
        "start_preconditions_passed": bool(preconditions and all(preconditions.values())),
        "subgoal_passed": bool(isinstance(subgoal, Mapping) and subgoal.get("passed") is True),
        "toggle_passed": bool(isinstance(toggle, Mapping) and toggle.get("success") is True),
        "fallback_actions_executed": len(action_log) if isinstance(action_log, list) else 0,
        "fallback_action_failure_count": action_failures,
        "target_discovery_step": fallback.get("discovery_step") if isinstance(fallback, Mapping) else None,
        "pickup_step": fallback.get("pickup_step") if isinstance(fallback, Mapping) else None,
        "coverage_actions_consumed": fallback.get("coverage_actions_consumed") if isinstance(fallback, Mapping) else None,
        "reset_restoration_passed": restoration.get("passed") is True,
        "task_integrity_passed": task_integrity,
        "diagnostic_passed": passed,
        "failure_reason": "" if passed else reason,
        "failure_classification": failure_classification,
        "fallback_capability_interpretable": bool(
            task_integrity and isinstance(action_log, list) and len(action_log) > 0
        ),
        "qualification_retry_allowed": passed,
        "memory_agents_run": False,
        "shared_variant_contract_unchanged": True,
        "memory_provider_changed": False,
        "prior_floorplan3_4_evidence_changed": False,
        "coordinates_exposed": False,
        "object_ids_exposed": False,
        "images_saved": False,
        "formal_use_allowed": False,
        "later_scenes_run": False,
        "next_gate": (
            "version and rerun FloorPlan5 qualification with this general visual fallback"
            if passed else
            "stop; do not rerun FloorPlan5 qualification or enter FloorPlan6"
        ),
        "output_dir": str(output_dir),
        **dict(git_state),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    git_state = _git_state()
    if git_state["working_tree_dirty"]:
        summary = {
            "diagnostic_passed": False,
            "failure_reason": "clean_worktree_required",
            "qualification_retry_allowed": False,
            **git_state,
        }
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 2

    plan = json.loads((PROJECT_ROOT / str(config["source_candidate_plan"])).read_text(encoding="utf-8"))
    qualification = json.loads((PROJECT_ROOT / str(config["source_qualification"])).read_text(encoding="utf-8"))
    candidate = validate_preconditions(config, plan, qualification)
    qualifier = _qualifier_module()
    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    try:
        qualifier._reset(env, "FloorPlan5")
        reachable_event = env.step({"action": "GetReachablePositions"})
        reachable = reachable_event.metadata.get("actionReturn")
        if (
            reachable_event.metadata.get("lastActionSuccess") is not True
            or not isinstance(reachable, list)
            or not reachable
        ):
            raise RuntimeError("GetReachablePositions failed")
        destination = candidate["destination_pose"]
        route = build_target_independent_visual_fallback_route(
            reachable_positions=reachable,
            start_position=destination,
            start_yaw=float(destination["rotation"]),
            start_camera_horizon_degrees=float(destination["horizon"]),
            grid_size=float(CONTROLLER_SETTINGS["gridSize"]),
            action_limit=VISUAL_FALLBACK_ACTION_LIMIT,
        )
        trial = qualifier._trial(
            env,
            scene="FloorPlan5",
            cup_id=str(plan["cup_object_id"]),
            machine_id=str(plan["coffee_machine_object_id"]),
            start_pose=candidate["start_pose"],
            subgoal_route=candidate["subgoal_route"],
            fallback_route=route,
            max_fallback_actions=VISUAL_FALLBACK_ACTION_LIMIT,
        )
        restoration = qualifier._restoration(
            env,
            scene="FloorPlan5",
            cup_id=str(plan["cup_object_id"]),
            machine_id=str(plan["coffee_machine_object_id"]),
            start_pose=candidate["start_pose"],
        )
    finally:
        env.close()

    private = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "boundary": BOUNDARY,
        "planner_visible": False,
        "candidate_order": 2,
        "candidate_plan_digest": plan["candidate_plan_digest"],
        "target_cup_object_id": plan["cup_object_id"],
        "coffee_machine_object_id": plan["coffee_machine_object_id"],
        "start_pose": candidate["start_pose"],
        "destination_pose": candidate["destination_pose"],
        "reachable_positions": reachable,
        "visual_fallback_route": route,
        "trial": trial,
        "reset_restoration": restoration,
        **git_state,
    }
    summary = build_public_summary(
        trial=trial,
        restoration=restoration,
        route=route,
        git_state=git_state,
        output_dir=output_dir,
    )
    _write_json(output_dir / "evaluator_only_visual_fallback.json", private)
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["diagnostic_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

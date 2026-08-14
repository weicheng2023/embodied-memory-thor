#!/usr/bin/env python3
"""Run one matched FloorPlan5 0-vs-30-degree fallback diagnostic."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


DIAGNOSTIC_VERSION = "phase5-r2-floorplan5-paired-horizon-v1"
BOUNDARY = "EVALUATOR-ONLY FLOORPLAN5 HORIZON DIAGNOSTIC - NEVER PLANNER INPUT"
DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "phase5_r2_floorplan5_paired_horizon_diagnostic_v1.json"
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
REMOVED_PHASES = (
    "coverage_absolute_horizon_alignment",
    "coverage_initial_horizon_restore",
)


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


def _qualifier_module() -> Any:
    path = PROJECT_ROOT / "scripts" / "qualify_phase5_r2.py"
    spec = importlib.util.spec_from_file_location("qualify_phase5_r2_v3_for_horizon", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load qualifier module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _one_candidate(rows: Any, order: int) -> Mapping[str, Any]:
    matches = [
        row for row in rows
        if isinstance(row, Mapping) and int(row.get("candidate_order", -1)) == order
    ] if isinstance(rows, list) else []
    if len(matches) != 1:
        raise ValueError("expected exactly one source candidate")
    return matches[0]


def _action_name(row: Mapping[str, Any]) -> str:
    action = row.get("action", {})
    return str(action.get("action", "")) if isinstance(action, Mapping) else ""


def build_downward_treatment_route(
    control: Mapping[str, Any], *, expected_control_count: int
) -> dict[str, Any]:
    """Remove only the 30->0 setup and 0->30 restore actions."""

    raw_actions = control.get("actions", [])
    if not isinstance(raw_actions, list) or len(raw_actions) != expected_control_count:
        raise ValueError("control fallback action count mismatch")
    if len(raw_actions) < 3:
        raise ValueError("control fallback is too short")
    first, last = raw_actions[0], raw_actions[-1]
    if not isinstance(first, Mapping) or not isinstance(last, Mapping):
        raise ValueError("control fallback boundary action is invalid")
    if (
        first.get("phase") != REMOVED_PHASES[0]
        or _action_name(first) != "LookUp"
        or last.get("phase") != REMOVED_PHASES[1]
        or _action_name(last) != "LookDown"
    ):
        raise ValueError("control fallback does not have the frozen horizon boundary")
    route = deepcopy(dict(control))
    route["actions"] = deepcopy(raw_actions[1:-1])
    route["route_version"] = "phase5-r2-paired-downward-treatment-v1"
    route["absolute_scan_horizon_degrees"] = 30.0
    route["diagnostic_only"] = True
    route["spatial_action_sequence_unchanged"] = True
    route.pop("route_digest", None)
    route["route_digest"] = stable_digest(route)
    return route


def validate_source(
    config: Mapping[str, Any], plan: Mapping[str, Any], qualification: Mapping[str, Any]
) -> Mapping[str, Any]:
    if config.get("diagnostic_version") != DIAGNOSTIC_VERSION:
        raise ValueError("diagnostic version mismatch")
    if config.get("scene") != "FloorPlan5":
        raise ValueError("diagnostic scene mismatch")
    if plan.get("candidate_plan_digest") != config.get("source_candidate_plan_digest"):
        raise ValueError("source candidate-plan digest mismatch")
    if qualification.get("code_revision") != config.get("source_revision"):
        raise ValueError("source qualification revision mismatch")
    candidate = _one_candidate(plan.get("candidate_pairs"), int(config["candidate_order"]))
    expected = {
        "start_pose_digest": candidate.get("start_pose_digest"),
        "destination_pose_digest": candidate.get("destination_pose_digest"),
        "subgoal_route_digest": candidate.get("subgoal_route_digest"),
        "subgoal_action_count": candidate.get("subgoal_route_action_count"),
        "control_fallback_route_digest": candidate.get("fallback_route_digest"),
        "control_fallback_action_count": candidate.get("fallback_route_action_count"),
    }
    for key, actual in expected.items():
        if config.get(key) != actual:
            raise ValueError(f"source candidate contract mismatch: {key}")
    trial = _one_candidate(qualification.get("trials"), int(config["candidate_order"]))
    first = trial.get("first_trial", {})
    fallback = first.get("fallback", {}) if isinstance(first, Mapping) else {}
    action_log = fallback.get("action_log", []) if isinstance(fallback, Mapping) else []
    if (
        trial.get("reason") != "target_not_rediscovered_before_fallback_exhaustion"
        or not isinstance(action_log, list)
        or len(action_log) != int(config["control_fallback_action_count"])
        or any(row.get("success") is not True for row in action_log if isinstance(row, Mapping))
    ):
        raise ValueError("source candidate is not the frozen clean fallback-exhaustion case")
    return candidate


def _arm_public(name: str, trial: Mapping[str, Any]) -> dict[str, Any]:
    fallback = trial.get("fallback", {}) if isinstance(trial, Mapping) else {}
    action_log = fallback.get("action_log", []) if isinstance(fallback, Mapping) else []
    preconditions = trial.get("preconditions", {}) if isinstance(trial, Mapping) else {}
    subgoal = trial.get("subgoal_route_replay", {}) if isinstance(trial, Mapping) else {}
    toggle = trial.get("toggle", {}) if isinstance(trial, Mapping) else {}
    return {
        "arm": name,
        "passed": trial.get("passed") is True,
        "reason": str(trial.get("reason", "")),
        "start_preconditions_passed": bool(
            isinstance(preconditions, Mapping) and all(preconditions.values())
        ),
        "subgoal_passed": bool(isinstance(subgoal, Mapping) and subgoal.get("passed") is True),
        "toggle_passed": bool(isinstance(toggle, Mapping) and toggle.get("success") is True),
        "fallback_actions_executed": len(action_log) if isinstance(action_log, list) else 0,
        "fallback_action_failure_count": sum(
            1 for row in action_log
            if isinstance(row, Mapping) and row.get("success") is not True
        ) if isinstance(action_log, list) else 0,
        "target_discovery_step": fallback.get("discovery_step") if isinstance(fallback, Mapping) else None,
        "target_lock_entered_count": fallback.get("target_lock_entered_count", 0)
        if isinstance(fallback, Mapping) else 0,
        "pickup_attempt_count": fallback.get("target_lock_pickup_attempt_count", 0)
        if isinstance(fallback, Mapping) else 0,
    }


def build_public_summary(
    *, arms: Sequence[Mapping[str, Any]], git_state: Mapping[str, Any], output_dir: Path
) -> dict[str, Any]:
    rows = [_arm_public(str(name), trial) for name, trial in arms]
    control, treatment = rows
    integrity = all(
        row["start_preconditions_passed"]
        and row["subgoal_passed"]
        and row["toggle_passed"]
        and row["fallback_action_failure_count"] == 0
        for row in rows
    )
    attribution = bool(integrity and not control["passed"] and treatment["passed"])
    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "claim_boundary": "one excluded matched FloorPlan5 horizon diagnostic; no memory variants or formal result",
        "scene": "FloorPlan5",
        "candidate_order": 2,
        "paired_order": [row["arm"] for row in rows],
        "fresh_reset_per_arm": True,
        "control_scan_horizon_degrees": 0.0,
        "treatment_scan_horizon_degrees": 30.0,
        "same_start_subgoal_toggle_and_spatial_fallback": True,
        "integrity_passed": integrity,
        "vertical_scan_coverage_attributed": attribution,
        "arms": rows,
        "memory_agents_run": False,
        "coordinates_exposed": False,
        "object_ids_exposed": False,
        "images_saved": False,
        "formal_use_allowed": False,
        "next_gate": (
            "precommit a general matched downward fallback revision before FloorPlan5 qualification retry"
            if attribution else
            "stop and inspect paired result; do not enter FloorPlan6"
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
        summary = {"integrity_passed": False, "failure_reason": "clean_worktree_required", **git_state}
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 2

    plan_path = PROJECT_ROOT / str(config["source_candidate_plan"])
    qualification_path = PROJECT_ROOT / str(config["source_qualification"])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
    candidate = validate_source(config, plan, qualification)
    control_route = deepcopy(candidate["fallback_route"])
    treatment_route = build_downward_treatment_route(
        control_route, expected_control_count=int(config["control_fallback_action_count"])
    )
    if len(treatment_route["actions"]) != int(config["treatment_fallback_action_count"]):
        raise ValueError("treatment fallback action count mismatch")
    control_spatial = control_route["actions"][1:-1]
    if stable_digest(control_spatial) != stable_digest(treatment_route["actions"]):
        raise ValueError("paired fallback spatial actions differ")

    qualifier = _qualifier_module()
    arms: list[tuple[str, Mapping[str, Any]]] = []
    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    try:
        for name, route in (
            ("control_0_degrees", control_route),
            ("treatment_downward_30_degrees", treatment_route),
        ):
            trial = qualifier._trial(
                env,
                scene="FloorPlan5",
                cup_id=str(plan["cup_object_id"]),
                machine_id=str(plan["coffee_machine_object_id"]),
                start_pose=candidate["start_pose"],
                subgoal_route=candidate["subgoal_route"],
                fallback_route=route,
            )
            arms.append((name, trial))
            print(json.dumps({"arm": name, "passed": trial.get("passed"), "reason": trial.get("reason")}, sort_keys=True), flush=True)
    finally:
        env.close()

    private = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "boundary": BOUNDARY,
        "planner_visible": False,
        "candidate_plan_digest": plan["candidate_plan_digest"],
        "candidate_order": config["candidate_order"],
        "start_pose": candidate["start_pose"],
        "target_cup_object_id": plan["cup_object_id"],
        "coffee_machine_object_id": plan["coffee_machine_object_id"],
        "control_route": control_route,
        "treatment_route": treatment_route,
        "arms": [{"arm": name, "trial": trial} for name, trial in arms],
        **git_state,
    }
    summary = build_public_summary(arms=arms, git_state=git_state, output_dir=output_dir)
    _write_json(output_dir / "evaluator_only_paired_horizon.json", private)
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["integrity_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

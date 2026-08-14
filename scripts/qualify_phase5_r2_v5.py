#!/usr/bin/env python3
"""Qualify one R2 scene with stable starts and exhaustive visual fallback."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.phase5.anchors import (  # noqa: E402
    VISUAL_FALLBACK_ACTION_LIMIT,
    VISUAL_FALLBACK_POLICY_VERSION,
    build_target_independent_visual_fallback_route,
    stable_digest,
)
from embodied_memory_thor.phase5.r2 import (  # noqa: E402
    build_task_subgoal_route,
)
from embodied_memory_thor.phase5.r2_stability import (  # noqa: E402
    STABILITY_OVERBOUND_SELECTION_POLICY,
    STABILITY_POSE_BUDGET,
    STABILITY_POLICY_VERSION,
    StabilityQueryError,
    attempt_reset_restoration,
    audit_start_pose_stability,
    first_coffee_machine_id,
    reset_restoration,
    select_first_standing_cup,
    select_stability_pose_budget,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


QUALIFICATION_VERSION = "phase5-r2-native-qualification-v5"
SCRIPT_VERSION = "phase5-r2-qualification-stable-visual-v5"
BOUNDARY = "EVALUATOR-ONLY R2 V5 QUALIFICATION - NEVER PLANNER INPUT"
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


def _legacy() -> Any:
    path = PROJECT_ROOT / "scripts" / "qualify_phase5_r2.py"
    spec = importlib.util.spec_from_file_location("phase5_r2_v3_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load audited R2 helper module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_state() -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    upstream = subprocess.run(
        ["git", "rev-parse", "@{upstream}"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    return {
        "code_revision": revision,
        "upstream_revision": upstream,
        "working_tree_dirty": dirty,
        "head_pushed": revision == upstream,
    }


def _candidate_pairs(
    cup_poses: Sequence[Mapping[str, Any]],
    machine_poses: Sequence[Mapping[str, Any]],
) -> list[tuple[int, int, Mapping[str, Any], Mapping[str, Any]]]:
    pairs = [
        (cup_order, machine_order, cup_pose, machine_pose)
        for cup_order, cup_pose in enumerate(cup_poses, start=1)
        for machine_order, machine_pose in enumerate(machine_poses, start=1)
    ]
    return sorted(
        pairs,
        key=lambda row: (max(row[0], row[1]), row[0] + row[1], row[0], row[1]),
    )[:MAX_CANDIDATE_PAIRS]


def classify_candidate_batch(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "native_batch_completed_without_qualified_configuration"
    reasons = [str(row.get("reason", "")) for row in rows]
    errors = [str(row.get("prebuild_error", "")) for row in rows]
    if all("visual fallback" in error for error in errors if error) and all(errors):
        return "visual_fallback_route_construction_ineligible"
    if all("subgoal" in error.lower() for error in errors if error) and all(errors):
        return "subgoal_route_construction_ineligible"
    if any(reason == "reset_restoration_failure" for reason in reasons):
        return "reset_restoration_failure"
    executed = [
        row.get("first_trial", {}) for row in rows
        if isinstance(row.get("first_trial"), Mapping)
    ]
    trial_reasons = [str(row.get("reason", "")) for row in executed]
    if trial_reasons and all(
        reason == "target_not_rediscovered_before_fallback_exhaustion"
        for reason in trial_reasons
    ):
        return "target_reacquisition_not_achieved_by_registered_visual_fallback"
    if any(reason == "fallback_route_action_failed" for reason in trial_reasons):
        return "visual_fallback_route_execution_ineligible"
    if any(reason == "subgoal_route_action_failed" for reason in trial_reasons):
        return "subgoal_route_execution_ineligible"
    return "native_batch_completed_without_qualified_configuration"


def _public_route(
    legacy: Any,
    *,
    route_id: str,
    scene: str,
    source_digest: str,
    route: Mapping[str, Any],
    role: str,
) -> dict[str, Any]:
    return legacy._public_route(
        route_id=route_id,
        scene=scene,
        source_digest=source_digest,
        route=route,
        route_role=role,
    )


def build_public_summary(
    *,
    scene: str,
    git_state: Mapping[str, Any],
    output_dir: Path,
    cup_audit: Sequence[Mapping[str, Any]],
    stability_audit: Sequence[Mapping[str, Any]],
    candidate_plan: Mapping[str, Any],
    trials: Sequence[Mapping[str, Any]],
    selected_public: Mapping[str, Any] | None,
    selected_private: Mapping[str, Any] | None,
    classification: str,
    failure_reason: str,
    restoration: Mapping[str, Any],
    pose_selection: Mapping[str, Any],
) -> dict[str, Any]:
    stable = [row for row in stability_audit if row.get("stable") is True]
    passed = selected_public is not None
    return {
        "qualification_version": QUALIFICATION_VERSION,
        "script_version": SCRIPT_VERSION,
        "claim_boundary": "single-scene evaluator qualification with stable starts and shared visual fallback; no memory variant or formal result",
        "scene": scene,
        "passed": passed,
        "failure_classification": "qualified" if passed else classification,
        "failure_reason": "" if passed else failure_reason,
        "scene_skip_allowed": not passed and classification in {
            "scene_start_ineligible_no_standing_cup",
            "scene_start_visibility_unstable_no_stable_pose",
            "scene_start_ineligible_no_joint_feasible_start",
            "subgoal_route_construction_ineligible",
            "subgoal_route_execution_ineligible",
            "visual_fallback_route_construction_ineligible",
            "visual_fallback_route_execution_ineligible",
            "native_batch_completed_without_qualified_configuration",
            "target_reacquisition_not_achieved_by_registered_visual_fallback",
            "candidate_batch_exhausted_without_route_or_replay_pass",
            "reset_restoration_passed_but_scene_ineligible",
        },
        "start_stability_policy_version": STABILITY_POLICY_VERSION,
        "trials_per_start_pose": 3,
        "selected_cup_order": next(
            (row["cup_order"] for row in cup_audit if row.get("selected") is True),
            None,
        ),
        "standing_pose_count": int(
            pose_selection.get("observed_pose_count", len(stability_audit))
        ),
        "selected_pose_count": int(
            pose_selection.get("selected_pose_count", len(stability_audit))
        ),
        "omitted_pose_count": int(pose_selection.get("omitted_pose_count", 0)),
        "pose_budget": int(
            pose_selection.get("pose_budget", STABILITY_POSE_BUDGET)
        ),
        "overbound_selection_policy": pose_selection.get(
            "selection_policy", STABILITY_OVERBOUND_SELECTION_POLICY
        ),
        "overbound_selection_applied": pose_selection.get(
            "selection_applied", False
        ) is True,
        "pose_selection_before_trial_outcomes": pose_selection.get(
            "selection_before_trial_outcomes", True
        ) is True,
        "pose_selection_digest": pose_selection.get("selection_digest"),
        "stable_start_pose_count": len(stable),
        "unstable_start_pose_count": sum(
            1 for row in stability_audit
            if row.get("classification") == "visibility_unstable"
        ),
        "ineligible_start_pose_count": sum(
            1 for row in stability_audit if row.get("classification") == "ineligible"
        ),
        "candidate_plan_digest": candidate_plan.get("candidate_plan_digest"),
        "candidate_pair_count": len(candidate_plan.get("candidate_pairs", [])),
        "candidate_trials_run": len(trials),
        "selected_candidate_order": (
            selected_private.get("candidate_order") if selected_private else None
        ),
        "configuration_id": (
            selected_public.get("configuration_id") if selected_public else None
        ),
        "start_pose_digest": (
            selected_public.get("start_pose_digest") if selected_public else None
        ),
        "subgoal_route": (
            selected_public.get("subgoal_route") if selected_public else None
        ),
        "fallback_route": (
            selected_public.get("fallback_route") if selected_public else None
        ),
        "fallback_policy_version": VISUAL_FALLBACK_POLICY_VERSION,
        "fallback_action_limit": VISUAL_FALLBACK_ACTION_LIMIT,
        "reset_restoration_passed": restoration.get("passed") is True,
        "candidate_freeze_before_task_outcomes": True,
        "fallback_target_or_anchor_input_used": False,
        "fallback_memory_variant_input_used": False,
        "coordinates_exposed": False,
        "object_ids_exposed": False,
        "memory_agents_run": False,
        "images_saved": False,
        "gui_enabled": False,
        "formal_use_allowed": False,
        "output_dir": str(output_dir),
        **dict(git_state),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    git_state = _git_state()
    if git_state["working_tree_dirty"] or not git_state["head_pushed"]:
        reason = "clean_worktree_required" if git_state["working_tree_dirty"] else "pushed_head_required"
        summary = {"passed": False, "failure_reason": reason, **git_state}
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 2

    legacy = _legacy()
    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    cup_id: str | None = None
    machine_id: str | None = None
    poses: Sequence[Mapping[str, Any]] = ()
    cup_audit: list[dict[str, Any]] = []
    stability_audit: list[dict[str, Any]] = []
    stable_poses: list[dict[str, Any]] = []
    pose_selection_public: Mapping[str, Any] = {}
    pose_selection_private: Mapping[str, Any] = {}
    candidate_plan: dict[str, Any] = {"candidate_pairs": []}
    trials: list[dict[str, Any]] = []
    selected_private: dict[str, Any] | None = None
    selected_public: dict[str, Any] | None = None
    restoration: Mapping[str, Any] = {"passed": False}
    classification = ""
    failure_reason = ""
    try:
        machine_id = first_coffee_machine_id(env, scene=args.scene)
        cup_id, poses, cup_audit = select_first_standing_cup(env, scene=args.scene)
        poses, pose_selection_public, pose_selection_private = (
            select_stability_pose_budget(poses)
        )
        if cup_id is None:
            classification = "scene_start_ineligible_no_standing_cup"
            failure_reason = "no pickupable Cup has a standing interactable pose"
            restoration = {"passed": True, "scope": "scene reset; no standing Cup selected"}
        else:
            stable_poses, stability_audit = audit_start_pose_stability(
                env,
                scene=args.scene,
                cup_id=cup_id,
                machine_id=machine_id,
                poses=poses,
            )
            restoration = reset_restoration(
                env, scene=args.scene, cup_id=cup_id, machine_id=machine_id
            )
            if restoration.get("passed") is not True:
                classification = "reset_restoration_failure"
                failure_reason = "stability audit reset restoration failed"
            elif not stable_poses:
                classification = "scene_start_visibility_unstable_no_stable_pose"
                failure_reason = "no standing Cup pose passed all three fresh-reset trials"
            else:
                machine_poses = legacy._query_poses(
                    env, scene=args.scene, object_id=machine_id
                )
                reachable = legacy._reachable(env, scene=args.scene)
                precommitted: list[dict[str, Any]] = []
                for order, (cup_order, machine_order, start, destination) in enumerate(
                    _candidate_pairs(stable_poses, machine_poses), start=1
                ):
                    row: dict[str, Any] = {
                        "candidate_order": order,
                        "stable_cup_pose_order": cup_order,
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
                        fallback_route = build_target_independent_visual_fallback_route(
                            reachable_positions=reachable,
                            start_position=destination,
                            start_yaw=float(destination["rotation"]),
                            start_camera_horizon_degrees=float(destination["horizon"]),
                            grid_size=float(CONTROLLER_SETTINGS["gridSize"]),
                            action_limit=VISUAL_FALLBACK_ACTION_LIMIT,
                        )
                        subgoal_count = len(legacy._actions(subgoal_route))
                        fallback_count = len(legacy._actions(fallback_route))
                        if subgoal_count > MAX_SUBGOAL_ACTIONS:
                            raise ValueError("subgoal route action limit exceeded")
                        row.update({
                            "prebuild_passed": True,
                            "subgoal_route": subgoal_route,
                            "subgoal_route_digest": stable_digest(subgoal_route),
                            "subgoal_route_action_count": subgoal_count,
                            "fallback_route": fallback_route,
                            "fallback_route_digest": stable_digest(fallback_route),
                            "fallback_route_action_count": fallback_count,
                        })
                    except Exception as exc:
                        row["prebuild_error"] = f"{type(exc).__name__}: {exc}"
                    precommitted.append(row)
                candidate_plan = {
                    "qualification_version": QUALIFICATION_VERSION,
                    "script_version": SCRIPT_VERSION,
                    "boundary": BOUNDARY,
                    "created_at": _utc_now(),
                    "created_before_native_trials": True,
                    "selection_uses_task_outcomes": False,
                    "scene": args.scene,
                    "cup_object_id": cup_id,
                    "coffee_machine_object_id": machine_id,
                    "stable_start_pose_count": len(stable_poses),
                    "pose_selection": dict(pose_selection_private),
                    "coffee_machine_pose_count": len(machine_poses),
                    "reachable_position_count": len(reachable),
                    "candidate_pair_limit": MAX_CANDIDATE_PAIRS,
                    "candidate_pairs": precommitted,
                    **git_state,
                }
                candidate_plan["candidate_plan_digest"] = stable_digest(candidate_plan)
                for raw in precommitted:
                    trial_row: dict[str, Any] = {
                        "candidate_order": raw["candidate_order"],
                        "prebuild_passed": raw["prebuild_passed"],
                        "prebuild_error": raw["prebuild_error"],
                    }
                    if not raw["prebuild_passed"]:
                        trial_row["reason"] = "candidate_prebuild_failed"
                        trials.append(trial_row)
                        continue
                    first = legacy._trial(
                        env,
                        scene=args.scene,
                        cup_id=cup_id,
                        machine_id=machine_id,
                        start_pose=raw["start_pose"],
                        subgoal_route=raw["subgoal_route"],
                        fallback_route=raw["fallback_route"],
                        max_fallback_actions=VISUAL_FALLBACK_ACTION_LIMIT,
                    )
                    trial_row["first_trial"] = first
                    replay = (
                        legacy._trial(
                            env,
                            scene=args.scene,
                            cup_id=cup_id,
                            machine_id=machine_id,
                            start_pose=raw["start_pose"],
                            subgoal_route=raw["subgoal_route"],
                            fallback_route=raw["fallback_route"],
                            max_fallback_actions=VISUAL_FALLBACK_ACTION_LIMIT,
                        )
                        if first["passed"] else
                        {"passed": False, "reason": "skipped_after_first_trial_failure"}
                    )
                    trial_row["fresh_reset_replay"] = replay
                    candidate_restoration = legacy._restoration(
                        env,
                        scene=args.scene,
                        cup_id=cup_id,
                        machine_id=machine_id,
                        start_pose=raw["start_pose"],
                    )
                    trial_row["reset_restoration"] = candidate_restoration
                    if candidate_restoration.get("passed") is not True:
                        trial_row["passed"] = False
                        trial_row["reason"] = "reset_restoration_failure"
                        trials.append(trial_row)
                        classification = "reset_restoration_failure"
                        failure_reason = "candidate reset restoration failed"
                        break
                    passed = bool(first["passed"] and replay["passed"])
                    trial_row["passed"] = passed
                    trial_row["reason"] = "" if passed else str(first.get("reason", ""))
                    trials.append(trial_row)
                    print(json.dumps({
                        "candidate_order": raw["candidate_order"],
                        "passed": passed,
                        "reason": trial_row["reason"],
                    }, sort_keys=True), flush=True)
                    if passed:
                        configuration_id = f"{args.scene}_R2_fixed_start_001"
                        source_digest = stable_digest({
                            "candidate_plan_digest": candidate_plan["candidate_plan_digest"],
                            "candidate_order": raw["candidate_order"],
                            "first_trial": first,
                            "fresh_reset_replay": replay,
                            "reset_restoration": candidate_restoration,
                        })
                        subgoal_public = _public_route(
                            legacy,
                            route_id=f"{configuration_id}_subgoal_v1",
                            scene=args.scene,
                            source_digest=source_digest,
                            route=raw["subgoal_route"],
                            role="task_subgoal_navigation",
                        )
                        fallback_public = _public_route(
                            legacy,
                            route_id=f"{configuration_id}_fallback_visual_v1",
                            scene=args.scene,
                            source_digest=source_digest,
                            route=raw["fallback_route"],
                            role="target_independent_fallback",
                        )
                        selected_private = {
                            "boundary": BOUNDARY,
                            "planner_visible": False,
                            "configuration_id": configuration_id,
                            "scene": args.scene,
                            "target_cup_object_id": cup_id,
                            "coffee_machine_object_id": machine_id,
                            "start_action": {"action": "TeleportFull", **dict(raw["start_pose"])},
                            "destination_pose": dict(raw["destination_pose"]),
                            "start_pose_digest": raw["start_pose_digest"],
                            "source_qualification_digest": source_digest,
                            "candidate_order": raw["candidate_order"],
                            "subgoal_route_private": raw["subgoal_route"],
                            "fallback_route_private": raw["fallback_route"],
                            "first_trial": first,
                            "fresh_reset_replay": replay,
                            "reset_restoration": candidate_restoration,
                        }
                        selected_public = {
                            "qualification_version": QUALIFICATION_VERSION,
                            "configuration_id": configuration_id,
                            "scene": args.scene,
                            "start_pose_digest": raw["start_pose_digest"],
                            "source_qualification_digest": source_digest,
                            "subgoal_route": subgoal_public,
                            "fallback_route": fallback_public,
                            "planner_visible_coordinates": False,
                            "formal_use_allowed": False,
                        }
                        restoration = candidate_restoration
                        classification = "qualified"
                        break
                if selected_public is None and classification != "reset_restoration_failure":
                    classification = classify_candidate_batch(trials)
                    failure_reason = "no candidate fully qualified"
    except StabilityQueryError as exc:
        classification = "stability_query_failure"
        failure_reason = f"{type(exc).__name__}: {exc}"
        restoration = attempt_reset_restoration(
            env,
            scene=args.scene,
            cup_id=cup_id,
            machine_id=machine_id,
        )
    except Exception as exc:
        classification = "qualification_script_exception"
        failure_reason = f"{type(exc).__name__}: {exc}"
        restoration = attempt_reset_restoration(
            env,
            scene=args.scene,
            cup_id=cup_id,
            machine_id=machine_id,
        )
    finally:
        env.close()

    private = {
        "qualification_version": QUALIFICATION_VERSION,
        "script_version": SCRIPT_VERSION,
        "boundary": BOUNDARY,
        "scene": args.scene,
        "target_cup_object_id": cup_id,
        "coffee_machine_object_id": machine_id,
        "cup_selection_audit": cup_audit,
        "stability_audit": stability_audit,
        "pose_selection": dict(pose_selection_private),
        "candidate_plan_digest": candidate_plan.get("candidate_plan_digest"),
        "trials": trials,
        "selected_configuration": selected_private,
        "reset_restoration": restoration,
        "failure_classification": classification,
        "failure_reason": failure_reason,
        **git_state,
    }
    _write_json(output_dir / "evaluator_only_candidate_plan.json", candidate_plan)
    _write_json(output_dir / "evaluator_only_qualification.json", private)
    if selected_public is not None:
        _write_json(output_dir / "public_qualified_configuration.json", selected_public)
        _write_json(output_dir / "evaluator_only_configuration_registry_draft.json", selected_private)
    summary = build_public_summary(
        scene=args.scene,
        git_state=git_state,
        output_dir=output_dir,
        cup_audit=cup_audit,
        stability_audit=stability_audit,
        candidate_plan=candidate_plan,
        trials=trials,
        selected_public=selected_public,
        selected_private=selected_private,
        classification=classification,
        failure_reason=failure_reason,
        restoration=restoration,
        pose_selection=pose_selection_public,
    )
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["passed"]:
        return 0
    return 1 if summary["scene_skip_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

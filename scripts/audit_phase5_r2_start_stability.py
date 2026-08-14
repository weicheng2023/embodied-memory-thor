#!/usr/bin/env python3
"""Audit one real R2 scene for deterministic three-reset start stability."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.phase5.r2_stability import (  # noqa: E402
    REQUIRED_PRECONDITIONS,
    STABILITY_OVERBOUND_SELECTION_POLICY,
    STABILITY_POSE_BUDGET,
    STABILITY_POLICY_VERSION,
    STABILITY_TRIALS_PER_POSE,
    StabilityQueryError,
    attempt_reset_restoration,
    audit_start_pose_stability,
    first_coffee_machine_id,
    reset_restoration,
    select_first_standing_cup,
    select_stability_pose_budget,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


BOUNDARY = "EVALUATOR-ONLY R2 START STABILITY - NEVER PLANNER INPUT"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "phase5_r2_start_visibility_stability_v2.json"
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


def validate_config(config: Mapping[str, Any]) -> None:
    if config.get("policy_version") != STABILITY_POLICY_VERSION:
        raise ValueError("R2 stability policy version mismatch")
    if int(config.get("trials_per_pose", 0)) != STABILITY_TRIALS_PER_POSE:
        raise ValueError("R2 stability trial count mismatch")
    if tuple(config.get("required_preconditions", [])) != REQUIRED_PRECONDITIONS:
        raise ValueError("R2 stability precondition schema mismatch")
    if int(config.get("pose_budget", 0)) != STABILITY_POSE_BUDGET:
        raise ValueError("R2 stability pose budget mismatch")
    if (
        config.get("overbound_selection_policy")
        != STABILITY_OVERBOUND_SELECTION_POLICY
    ):
        raise ValueError("R2 stability over-bound selection policy mismatch")
    if config.get("memory_agents_run") is not False:
        raise ValueError("stability audit cannot run memory agents")
    if config.get("images_saved") is not False:
        raise ValueError("stability audit cannot save images")


def build_public_summary(
    *,
    scene: str,
    poses: Sequence[Mapping[str, Any]],
    audit: Sequence[Mapping[str, Any]],
    cup_audit: Sequence[Mapping[str, Any]],
    restoration: Mapping[str, Any],
    pose_selection: Mapping[str, Any],
    git_state: Mapping[str, Any],
    output_dir: Path,
    failure_reason: str = "",
) -> dict[str, Any]:
    stable = [row for row in audit if row.get("stable") is True]
    unstable_count = sum(
        1 for row in audit if row.get("classification") == "visibility_unstable"
    )
    ineligible_count = sum(
        1 for row in audit if row.get("classification") == "ineligible"
    )
    if failure_reason:
        classification = "stability_query_failure"
        completed = False
        scene_skip_allowed = False
    elif not poses:
        classification = "scene_start_ineligible_no_standing_cup"
        completed = True
        scene_skip_allowed = True
    elif not stable:
        classification = "scene_start_visibility_unstable_no_stable_pose"
        completed = True
        scene_skip_allowed = True
    else:
        classification = "start_visibility_stability_passed"
        completed = True
        scene_skip_allowed = False
    return {
        "policy_version": STABILITY_POLICY_VERSION,
        "claim_boundary": "evaluator-only R2 start stability; no routes, interaction, planner, memory variant, image, or formal result",
        "scene": scene,
        "completed": completed,
        "classification": classification,
        "failure_reason": failure_reason,
        "scene_skip_allowed": scene_skip_allowed,
        "trials_per_pose": STABILITY_TRIALS_PER_POSE,
        "selected_cup_order": next(
            (row["cup_order"] for row in cup_audit if row.get("selected") is True),
            None,
        ),
        "standing_pose_count": int(
            pose_selection.get("observed_pose_count", len(poses))
        ),
        "selected_pose_count": int(
            pose_selection.get("selected_pose_count", len(poses))
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
        "pose_trials_run": sum(len(row.get("trials", [])) for row in audit),
        "stable_pose_count": len(stable),
        "unstable_pose_count": unstable_count,
        "ineligible_pose_count": ineligible_count,
        "first_stable_pose_order": stable[0]["pose_order"] if stable else None,
        "first_stable_pose_digest": stable[0]["pose_digest"] if stable else None,
        "reset_restoration_passed": restoration.get("passed") is True,
        "coordinates_exposed": False,
        "object_ids_exposed": False,
        "routes_built_or_executed": False,
        "coffee_machine_pose_query_run": False,
        "interaction_actions_run": False,
        "planner_run": False,
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
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    validate_config(config)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    git_state = _git_state()
    if git_state["working_tree_dirty"] or not git_state["head_pushed"]:
        reason = (
            "clean_worktree_required" if git_state["working_tree_dirty"]
            else "pushed_head_required"
        )
        summary = {"completed": False, "failure_reason": reason, **git_state}
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 2

    cup_id: str | None = None
    machine_id: str | None = None
    poses: Sequence[Mapping[str, Any]] = ()
    cup_audit: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    pose_selection_public: Mapping[str, Any] = {}
    pose_selection_private: Mapping[str, Any] = {}
    restoration: Mapping[str, Any] = {"passed": False}
    failure_reason = ""
    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    try:
        machine_id = first_coffee_machine_id(env, scene=args.scene)
        cup_id, poses, cup_audit = select_first_standing_cup(env, scene=args.scene)
        poses, pose_selection_public, pose_selection_private = (
            select_stability_pose_budget(poses)
        )
        if cup_id is not None:
            _, audit = audit_start_pose_stability(
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
                failure_reason = "reset_restoration_failure"
        else:
            restoration = {"passed": True, "scope": "scene reset; no standing Cup selected"}
    except StabilityQueryError as exc:
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
        "policy_version": STABILITY_POLICY_VERSION,
        "boundary": BOUNDARY,
        "planner_visible": False,
        "scene": args.scene,
        "target_cup_object_id": cup_id,
        "coffee_machine_object_id": machine_id,
        "cup_selection_audit": cup_audit,
        "poses": list(poses),
        "pose_selection": dict(pose_selection_private),
        "pose_audit": audit,
        "reset_restoration": restoration,
        "failure_reason": failure_reason,
        **git_state,
    }
    summary = build_public_summary(
        scene=args.scene,
        poses=poses,
        audit=audit,
        cup_audit=cup_audit,
        restoration=restoration,
        pose_selection=pose_selection_public,
        git_state=git_state,
        output_dir=output_dir,
        failure_reason=failure_reason,
    )
    _write_json(output_dir / "evaluator_only_stability.json", private)
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["completed"] and summary["reset_restoration_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

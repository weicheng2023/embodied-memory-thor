#!/usr/bin/env python3
"""Execute one frozen route in a fresh-reset no-placement baseline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SCRIPT_ROOT = PROJECT_ROOT / "scripts"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402
from diagnose_phase5_route_mutation import replay_route  # noqa: E402
from qualify_phase5_anchors import (  # noqa: E402
    CONTROLLER_SETTINGS,
    STABILITY_TOLERANCE_METERS,
    _load_private_start,
    _position,
    _reset_setup,
    _target,
    _visible_book,
    _xz_distance,
)


SCRIPT_VERSION = "phase5-baseline-route-execution-v1"
BOUNDARY = "EVALUATOR-ONLY BASELINE ROUTE EXECUTION - NEVER PLANNER INPUT"
MATCHED_PASS_COUNT = 4


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


def classify_execution(
    route_result: Mapping[str, Any],
    *,
    precondition_passed: bool,
    reset_restoration_passed: bool,
    fatal_error: str,
) -> dict[str, Any]:
    if fatal_error or not precondition_passed or not reset_restoration_passed:
        return {
            "passed": False,
            "classification": "baseline_route_execution_invalid",
            "scene_skip_allowed": False,
        }
    if route_result.get("route_completed") is not True:
        return {
            "passed": False,
            "classification": "route_execution_ineligible",
            "scene_skip_allowed": True,
        }
    return {
        "passed": True,
        "classification": "baseline_route_execution_passed",
        "scene_skip_allowed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--start-registry", type=Path, action="append", required=True)
    parser.add_argument("--route-file", type=Path, required=True)
    parser.add_argument("--route-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    git_state = _git_state()
    if git_state["working_tree_dirty"]:
        summary = {
            "passed": False,
            "classification": "baseline_route_execution_invalid",
            "failure_reason": "clean_worktree_required",
            **git_state,
        }
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 2

    route = json.loads(args.route_file.resolve().read_text(encoding="utf-8"))
    route_summary = json.loads(
        args.route_summary.resolve().read_text(encoding="utf-8")
    )
    route_digest = stable_digest(route)
    route_count = len(route.get("actions", []))
    if (
        route_summary.get("passed") is not True
        or route_summary.get("scene") != args.scene
        or route_summary.get("route_digest") != route_digest
        or route_summary.get("route_action_count") != route_count
        or route_summary.get("code_revision") != git_state["code_revision"]
    ):
        raise ValueError("route file/summary/current revision contract mismatch")
    start = _load_private_start(
        [path.resolve() for path in args.start_registry], args.scene
    )
    pose = dict(start["selected_pose"])
    if stable_digest(pose) != start["selected_pose_digest"]:
        raise ValueError("private start pose digest mismatch")
    if route_summary.get("start_pose_digest") != start["selected_pose_digest"]:
        raise ValueError("route summary does not bind the private start")
    setup_actions = ({"action": "TeleportFull", **pose},)

    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    route_result: dict[str, Any] = {}
    fatal_error = ""
    precondition_passed = False
    restoration: dict[str, Any] = {"passed": False}
    private_target_id = ""
    private_target_position: Mapping[str, Any] | None = None
    pass_log: list[dict[str, Any]] = []
    try:
        metadata, setup_log = _reset_setup(env, args.scene, setup_actions)
        book = _visible_book(metadata)
        private_target_id = str(book["objectId"])
        private_target_position = _position(book)
        for index in range(1, MATCHED_PASS_COUNT + 1):
            event = env.step({"action": "Pass"})
            pass_log.append({
                "index": index,
                "success": bool(event.metadata.get("lastActionSuccess", False)),
                "error": str(event.metadata.get("errorMessage", "")),
            })
            if not pass_log[-1]["success"]:
                break
        current = _target(env.get_evaluator_state(), private_target_id)
        current_position = _position(current)
        precondition_passed = bool(
            len(pass_log) == MATCHED_PASS_COUNT
            and all(row["success"] for row in pass_log)
            and current is not None
            and current.get("visible") is True
            and private_target_position is not None
            and current_position is not None
            and _xz_distance(private_target_position, current_position)
            <= STABILITY_TOLERANCE_METERS
        )
        if precondition_passed:
            route_result = replay_route(env, route, probe_step=route_count)
        else:
            route_result = {
                "route_action_count": route_count,
                "route_actions_attempted": 0,
                "route_completed": False,
                "first_failed_route_step": None,
                "failed_action_name": "",
                "failed_route_phase": "",
                "blocker_object_type": "",
                "action_log": [],
            }
        restored_metadata, restoration_setup = _reset_setup(
            env, args.scene, setup_actions
        )
        restored = _target(restored_metadata, private_target_id)
        restored_position = _position(restored)
        restoration_delta = (
            _xz_distance(private_target_position, restored_position)
            if private_target_position is not None and restored_position is not None
            else None
        )
        restoration = {
            "passed": bool(
                restored is not None
                and restored.get("visible") is True
                and restoration_delta is not None
                and restoration_delta <= STABILITY_TOLERANCE_METERS
            ),
            "position_delta_xz_meters": restoration_delta,
            "setup": restoration_setup,
        }
    except Exception as exc:
        setup_log = []
        fatal_error = f"{type(exc).__name__}: {exc}"
    finally:
        env.close()

    decision = classify_execution(
        route_result,
        precondition_passed=precondition_passed,
        reset_restoration_passed=bool(restoration.get("passed")),
        fatal_error=fatal_error,
    )
    private = {
        "execution_version": SCRIPT_VERSION,
        "boundary": BOUNDARY,
        "scene": args.scene,
        "configuration_id": route_summary.get("configuration_id"),
        "start_pose_digest": start["selected_pose_digest"],
        "route_digest": route_digest,
        "route_action_count": route_count,
        "matched_pass_count": MATCHED_PASS_COUNT,
        "setup_log": setup_log,
        "pass_log": pass_log,
        "precondition_passed": precondition_passed,
        "target_object_id": private_target_id,
        "target_before_position": private_target_position,
        "route_result": route_result,
        "reset_restoration": restoration,
        "fatal_error": fatal_error,
        **decision,
        **git_state,
    }
    private_digest = stable_digest(private)
    private["private_execution_digest"] = private_digest
    _write_json(output_dir / "evaluator_only_baseline_route_execution.json", private)
    summary = {
        "execution_version": SCRIPT_VERSION,
        "claim": "fresh-reset no-placement baseline route execution; not anchor qualification or memory comparison",
        "scene": args.scene,
        "configuration_id": route_summary.get("configuration_id"),
        "start_pose_digest": start["selected_pose_digest"],
        "route_version": route.get("route_version"),
        "route_digest": route_digest,
        "route_action_count": route_count,
        "matched_pass_count": MATCHED_PASS_COUNT,
        "precondition_passed": precondition_passed,
        "route_actions_attempted": route_result.get("route_actions_attempted", 0),
        "route_completed": route_result.get("route_completed", False),
        "first_failed_route_step": route_result.get("first_failed_route_step"),
        "failed_action_name": route_result.get("failed_action_name", ""),
        "failed_route_phase": route_result.get("failed_route_phase", ""),
        "blocker_object_type": route_result.get("blocker_object_type", ""),
        "reset_restoration_passed": restoration.get("passed", False),
        "fatal_error": fatal_error,
        **decision,
        "support_queries_run": False,
        "placement_actions_run": False,
        "planner_run": False,
        "memory_agents_run": False,
        "images_saved": False,
        "obstacle_recovery_actions_run": False,
        "coordinates_exposed": False,
        "private_execution_digest": private_digest,
        **git_state,
    }
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if decision["classification"] != "baseline_route_execution_invalid" else 2


if __name__ == "__main__":
    raise SystemExit(main())

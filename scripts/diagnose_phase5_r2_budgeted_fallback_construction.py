#!/usr/bin/env python3
"""Construct (but never execute) one Phase 5 R2 budgeted fallback route."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.phase5.budgeted_fallback import (  # noqa: E402
    BUDGETED_VISUAL_FALLBACK_ACTION_LIMIT,
    BUDGETED_VISUAL_FALLBACK_BIN_SIZE_STEPS,
    BUDGETED_VISUAL_FALLBACK_POLICY_VERSION,
    BUDGETED_VISUAL_FALLBACK_SELECTION_POLICY,
    BudgetedVisualFallbackConstructionError,
    build_target_independent_budgeted_visual_fallback_route,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


DIAGNOSTIC_VERSION = "phase5-r2-budgeted-visual-fallback-construction-v1"
BOUNDARY = "EVALUATOR-ONLY REACHABLE GRAPH AND START POSE - NEVER PLANNER INPUT"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "phase5_r2_budgeted_visual_fallback_v1.json"
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _validate_config(config: Mapping[str, Any], scene: str) -> None:
    expected = {
        "policy_version": BUDGETED_VISUAL_FALLBACK_POLICY_VERSION,
        "viewpoint_selection_policy": BUDGETED_VISUAL_FALLBACK_SELECTION_POLICY,
        "bin_size_steps": BUDGETED_VISUAL_FALLBACK_BIN_SIZE_STEPS,
        "action_limit": BUDGETED_VISUAL_FALLBACK_ACTION_LIMIT,
        "stop_after_first_construction_pass": True,
        "route_execution_allowed": False,
        "qualification_allowed": False,
        "memory_variants_allowed": False,
        "images_allowed": False,
        "formal_statistics_allowed": False,
        "floorplan17_or_later_allowed": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"budgeted fallback config mismatch: {key}")
    scenes = config.get("construction_diagnostic_scene_order")
    if not isinstance(scenes, list) or scene not in scenes:
        raise ValueError("scene is outside the pre-registered diagnostic order")
    if config.get("shared_variant_contract") != [
        "no_memory", "short_memory_k2", "object_memory"
    ]:
        raise ValueError("shared-variant contract mismatch")
    for relative, expected_hash in config.get("historical_artifacts_frozen", {}).items():
        if _sha256(PROJECT_ROOT / str(relative)) != str(expected_hash):
            raise ValueError(f"historical artifact changed: {relative}")


def _agent_start(metadata: Mapping[str, Any]) -> tuple[Mapping[str, Any], float, float]:
    agent = metadata.get("agent")
    if not isinstance(agent, Mapping):
        raise RuntimeError("reset metadata has no agent pose")
    position = agent.get("position")
    rotation = agent.get("rotation")
    if not isinstance(position, Mapping) or not isinstance(rotation, Mapping):
        raise RuntimeError("reset metadata has an incomplete agent pose")
    return position, float(rotation["y"]), float(agent["cameraHorizon"])


def _summary(
    *,
    scene: str,
    classification: str,
    route: Mapping[str, Any] | None,
    failure_reason: str,
    restoration_passed: bool,
    git_state: Mapping[str, Any],
) -> dict[str, Any]:
    coverage = route.get("coverage_summary") if route else {
        "occupied_bin_count": None,
        "occupied_bins_with_viewpoint_count": None,
        "all_occupied_bins_represented": False,
        "maximum_within_bin_grid_chebyshev_distance": None,
        "line_of_sight_coverage_claimed": False,
    }
    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "policy_version": BUDGETED_VISUAL_FALLBACK_POLICY_VERSION,
        "claim_boundary": "route construction only; no route execution, qualification, memory variant, image, or formal result",
        "scene": scene,
        "action_limit": BUDGETED_VISUAL_FALLBACK_ACTION_LIMIT,
        "action_count": route.get("action_count") if route else None,
        "viewpoint_count": route.get("viewpoint_count") if route else None,
        "route_digest": route.get("route_digest") if route else None,
        "coverage_summary": coverage,
        "classification": classification,
        "failure_reason": failure_reason,
        "reset_restoration_passed": restoration_passed,
        "coordinates_exposed": False,
        "object_ids_exposed": False,
        "reachable_graph_exposed": False,
        "route_actions_executed": False,
        "qualification_run": False,
        "memory_variants_run": False,
        "images_saved": False,
        "formal_use_allowed": False,
        **dict(git_state),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    _validate_config(config, args.scene)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    git_state = _git_state()
    if git_state["working_tree_dirty"] or not git_state["head_pushed"]:
        reason = (
            "clean_worktree_required" if git_state["working_tree_dirty"]
            else "pushed_head_required"
        )
        summary = _summary(
            scene=args.scene,
            classification="diagnostic_integrity_failure",
            route=None,
            failure_reason=reason,
            restoration_passed=False,
            git_state=git_state,
        )
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 2

    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    route: dict[str, Any] | None = None
    reachable: list[Mapping[str, Any]] = []
    start_position: Mapping[str, Any] | None = None
    start_yaw: float | None = None
    start_horizon: float | None = None
    failure_reason = ""
    classification = str(config["construction_pass_classification"])
    restoration_passed = False
    exit_code = 0
    try:
        reset_event = env.reset(args.scene)
        start_position, start_yaw, start_horizon = _agent_start(reset_event.metadata)
        reachable_event = env.step({"action": "GetReachablePositions"})
        action_return = reachable_event.metadata.get("actionReturn")
        if (
            reachable_event.metadata.get("lastActionSuccess") is not True
            or not isinstance(action_return, list)
            or not action_return
        ):
            raise RuntimeError("GetReachablePositions failed")
        reachable = action_return
        try:
            route = build_target_independent_budgeted_visual_fallback_route(
                reachable_positions=reachable,
                start_position=start_position,
                start_yaw=start_yaw,
                start_camera_horizon_degrees=start_horizon,
                grid_size=float(config["grid_size_meters"]),
                bin_size_steps=int(config["bin_size_steps"]),
                action_limit=int(config["action_limit"]),
            )
        except BudgetedVisualFallbackConstructionError as exc:
            route = exc.route
            failure_reason = str(exc)
            classification = str(config["construction_failure_classification"])
            exit_code = 1
        restoration_event = env.reset(args.scene)
        restoration_passed = bool(
            restoration_event.metadata.get("lastActionSuccess") is True
            and restoration_event.metadata.get("sceneName") == args.scene
        )
        if not restoration_passed:
            classification = "diagnostic_integrity_failure"
            failure_reason = "reset_restoration_failed"
            exit_code = 2
    except Exception as exc:
        classification = "diagnostic_integrity_failure"
        failure_reason = str(exc)
        exit_code = 2
    finally:
        env.close()

    private = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "boundary": BOUNDARY,
        "planner_visible": False,
        "scene": args.scene,
        "start_position": start_position,
        "start_yaw": start_yaw,
        "start_camera_horizon": start_horizon,
        "reachable_positions": reachable,
        "route": route,
        "failure_reason": failure_reason,
        **git_state,
    }
    summary = _summary(
        scene=args.scene,
        classification=classification,
        route=route,
        failure_reason=failure_reason,
        restoration_passed=restoration_passed,
        git_state=git_state,
    )
    _write_json(output_dir / "evaluator_only_construction.json", private)
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

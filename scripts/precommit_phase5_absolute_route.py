#!/usr/bin/env python3
"""Precommit one coordinate-free absolute-horizon route without placement."""

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
from embodied_memory_thor.phase5.anchors import (  # noqa: E402
    build_target_independent_coverage_route,
    stable_digest,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402
from qualify_phase5_anchors import (  # noqa: E402
    CONTROLLER_SETTINGS,
    MAX_FALLBACK_ACTIONS,
    _load_candidate_contract,
    _load_private_start,
)


SCRIPT_VERSION = "phase5-absolute-route-precommit-v1"


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


def _coordinate_free_summary(
    *,
    scene: str,
    configuration_id: str,
    start_pose_digest: str,
    route: Mapping[str, Any],
    git_state: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    actions = route.get("actions", [])
    action_count = len(actions) if isinstance(actions, list) else 0
    return {
        "precommit_version": SCRIPT_VERSION,
        "claim": "route-only setup QA; no placement, anchor, or memory agent",
        "scene": scene,
        "configuration_id": configuration_id,
        "start_pose_digest": start_pose_digest,
        "route_version": route.get("route_version"),
        "route_digest": stable_digest(route),
        "route_action_count": action_count,
        "route_action_limit": MAX_FALLBACK_ACTIONS,
        "passed": action_count <= MAX_FALLBACK_ACTIONS,
        "failure_reason": (
            "" if action_count <= MAX_FALLBACK_ACTIONS else "route_action_limit_exceeded"
        ),
        "absolute_scan_horizon_degrees": route.get(
            "absolute_scan_horizon_degrees"
        ),
        "horizon_alignment_action_count": route.get(
            "horizon_alignment_action_count"
        ),
        "horizon_restoration_action_count": route.get(
            "horizon_restoration_action_count"
        ),
        "target_or_anchor_input_used": route.get("target_or_anchor_input_used"),
        "placement_actions_run": False,
        "memory_agents_run": False,
        "images_saved": False,
        "coordinates_exposed_in_summary": False,
        "output_dir": str(output_dir),
        **dict(git_state),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--candidate-contract", type=Path)
    parser.add_argument("--configuration-id")
    parser.add_argument("--start-registry", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--absolute-scan-horizon-degrees", type=float, default=0.0)
    args = parser.parse_args(argv)

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    git_state = _git_state()
    if git_state["working_tree_dirty"] is not False:
        summary = {
            "passed": False,
            "failure_reason": "clean_worktree_required",
            **git_state,
        }
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 2

    contract = (
        _load_candidate_contract(args.candidate_contract.resolve(), args.scene)
        if args.candidate_contract is not None
        else None
    )
    if contract is None and not args.configuration_id:
        parser.error("--configuration-id is required without --candidate-contract")
    start = _load_private_start(
        [path.resolve() for path in args.start_registry], args.scene
    )
    pose = dict(start["selected_pose"])
    pose_digest = stable_digest(pose)
    if pose_digest != start["selected_pose_digest"]:
        raise ValueError("private start pose does not match its retained digest")
    if contract is not None and pose_digest != contract.get("start_pose_digest"):
        raise ValueError("private start pose does not match the public contract")

    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    try:
        env.reset(args.scene)
        teleport = env.step({"action": "TeleportFull", **pose})
        if teleport.metadata.get("lastActionSuccess") is not True:
            raise RuntimeError("frozen start teleport failed")
        metadata = env.get_evaluator_state()
        reachable_event = env.step({"action": "GetReachablePositions"})
        reachable_raw = reachable_event.metadata.get("actionReturn")
        reachable = (
            [dict(item) for item in reachable_raw if isinstance(item, Mapping)]
            if isinstance(reachable_raw, list)
            else []
        )
        if reachable_event.metadata.get("lastActionSuccess") is not True or not reachable:
            raise RuntimeError("GetReachablePositions failed")
        agent = metadata.get("agent", {})
        route = build_target_independent_coverage_route(
            reachable_positions=reachable,
            start_position=agent.get("position", {}),
            start_yaw=float(agent.get("rotation", {}).get("y", 0.0)),
            grid_size=float(CONTROLLER_SETTINGS["gridSize"]),
            start_camera_horizon_degrees=float(
                agent.get("cameraHorizon", 0.0)
            ),
            absolute_scan_horizon_degrees=args.absolute_scan_horizon_degrees,
        )
    finally:
        env.close()

    _write_json(output_dir / "evaluator_only_coverage_route.json", route)
    summary = _coordinate_free_summary(
        scene=args.scene,
        configuration_id=(
            str(contract["configuration_id"])
            if contract is not None
            else str(args.configuration_id)
        ),
        start_pose_digest=pose_digest,
        route=route,
        git_state=git_state,
        output_dir=output_dir,
    )
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

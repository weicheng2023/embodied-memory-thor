#!/usr/bin/env python3
"""Exhaustively audit FloorPlan5 ordered-task start visibility only."""

from __future__ import annotations

import argparse
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
from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.phase5.r2 import (  # noqa: E402
    normalize_interactable_pose,
    pose_sort_key,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


CENSUS_VERSION = "phase5-r2-start-visibility-census-v1"
BOUNDARY = "EVALUATOR-ONLY R2 START VISIBILITY CENSUS - NEVER PLANNER INPUT"
DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "phase5_r2_floorplan5_start_visibility_census_v1.json"
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


def _objects(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = metadata.get("objects", [])
    return [row for row in raw if isinstance(row, Mapping)] if isinstance(raw, list) else []


def _object(metadata: Mapping[str, Any], object_id: str) -> Mapping[str, Any] | None:
    return next((row for row in _objects(metadata) if row.get("objectId") == object_id), None)


def _sorted_targets(
    metadata: Mapping[str, Any], *, object_type: str, predicate: str
) -> list[Mapping[str, Any]]:
    rows = sorted(
        (
            row for row in _objects(metadata)
            if row.get("objectType") == object_type
            and row.get(predicate) is True and row.get("objectId")
        ),
        key=lambda row: str(row["objectId"]),
    )
    if not rows:
        raise RuntimeError(f"no {predicate} {object_type} exists after reset")
    return rows


def _reset_metadata(env: Any, scene: str) -> Mapping[str, Any]:
    env.reset(scene)
    metadata = env.get_evaluator_state()
    return metadata if isinstance(metadata, Mapping) else {}


def select_first_standing_cup(
    env: Any, *, scene: str
) -> tuple[str, tuple[dict[str, Any], ...], list[dict[str, Any]]]:
    cups = _sorted_targets(
        _reset_metadata(env, scene), object_type="Cup", predicate="pickupable"
    )
    audit: list[dict[str, Any]] = []
    for cup_order, cup in enumerate(cups, start=1):
        object_id = str(cup["objectId"])
        _reset_metadata(env, scene)
        event = env.step({"action": "GetInteractablePoses", "objectId": object_id})
        success = event.metadata.get("lastActionSuccess") is True
        if not success:
            raise RuntimeError(
                f"GetInteractablePoses failed for Cup order {cup_order}: "
                + str(event.metadata.get("errorMessage", ""))
            )
        raw = event.metadata.get("actionReturn") or []
        poses = tuple(sorted(
            (
                pose for pose in (
                    normalize_interactable_pose(row)
                    for row in raw if isinstance(row, Mapping)
                )
                if pose is not None and pose["standing"] is True
            ),
            key=pose_sort_key,
        ))
        audit.append({
            "cup_order": cup_order,
            "object_id": object_id,
            "fresh_reset_before_query": True,
            "query_success": True,
            "standing_pose_count": len(poses),
            "selected": bool(poses),
        })
        if poses:
            return object_id, poses, audit
    raise RuntimeError("no pickupable Cup has a standing interactable pose")


def audit_start_poses(
    env: Any,
    *,
    scene: str,
    cup_id: str,
    machine_id: str,
    poses: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Evaluate every pose after its own reset; no task action is allowed."""

    rows: list[dict[str, Any]] = []
    for pose_order, pose in enumerate(poses, start=1):
        _reset_metadata(env, scene)
        event = env.step({"action": "TeleportFull", **dict(pose)})
        metadata = event.metadata
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
        rows.append({
            "pose_order": pose_order,
            "pose": dict(pose),
            "pose_digest": stable_digest(pose),
            "fresh_reset_before_teleport": True,
            "preconditions": preconditions,
            "eligible": all(preconditions.values()),
        })
    return rows


def build_public_summary(
    *, config: Mapping[str, Any], rows: Sequence[Mapping[str, Any]],
    cup_audit: Sequence[Mapping[str, Any]], git_state: Mapping[str, Any], output_dir: Path,
) -> dict[str, Any]:
    eligible = [row for row in rows if row.get("eligible") is True]
    field_pass_counts = {
        field: sum(
            1 for row in rows
            if isinstance(row.get("preconditions"), Mapping)
            and row["preconditions"].get(field) is True
        )
        for field in config["required_preconditions"]
    }
    return {
        "census_version": CENSUS_VERSION,
        "claim_boundary": "FloorPlan5 evaluator-only start-feasibility census; no route, interaction, planner, memory variant, or formal result",
        "scene": config["scene"],
        "completed": True,
        "standing_pose_count": len(rows),
        "pose_trials_run": len(rows),
        "fresh_reset_per_pose": True,
        "selected_cup_order": next(
            row["cup_order"] for row in cup_audit if row["selected"]
        ),
        "eligible_pose_count": len(eligible),
        "first_eligible_pose_order": (
            eligible[0]["pose_order"] if eligible else None
        ),
        "first_eligible_pose_digest": (
            eligible[0]["pose_digest"] if eligible else None
        ),
        "precondition_pass_counts": field_pass_counts,
        "coordinates_exposed": False,
        "object_ids_exposed": False,
        "memory_agents_run": False,
        "routes_built_or_executed": False,
        "coffee_machine_pose_query_run": False,
        "images_saved": False,
        "formal_use_allowed": False,
        "next_gate": (
            "precommit start-feasible pose filtering before rank-balanced pairing"
            if eligible else
            "classify FloorPlan5 structural ordered-start-ineligible and continue FloorPlan6"
        ),
        "output_dir": str(output_dir),
        **dict(git_state),
    }


def validate_config(config: Mapping[str, Any]) -> None:
    if config.get("census_version") != CENSUS_VERSION or config.get("scene") != "FloorPlan5":
        raise ValueError("FloorPlan5 start-census identity mismatch")
    if config.get("fresh_reset_per_pose") is not True:
        raise ValueError("start census requires fresh reset per pose")
    if int(config.get("maximum_pose_trials", 0)) != 256:
        raise ValueError("start census pose bound mismatch")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    validate_config(config)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    git_state = _git_state()
    if git_state["working_tree_dirty"]:
        summary = {"completed": False, "failure_reason": "clean_worktree_required", **git_state}
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 2

    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    try:
        scene = str(config["scene"])
        initial = _reset_metadata(env, scene)
        machine_id = str(_sorted_targets(
            initial, object_type="CoffeeMachine", predicate="toggleable"
        )[0]["objectId"])
        cup_id, poses, cup_audit = select_first_standing_cup(env, scene=scene)
        if len(poses) > int(config["maximum_pose_trials"]):
            raise RuntimeError("standing pose count exceeds precommitted bound")
        rows = audit_start_poses(
            env, scene=scene, cup_id=cup_id, machine_id=machine_id, poses=poses
        )
    finally:
        env.close()

    private = {
        "census_version": CENSUS_VERSION,
        "boundary": BOUNDARY,
        "planner_visible": False,
        "scene": config["scene"],
        "target_cup_object_id": cup_id,
        "coffee_machine_object_id": machine_id,
        "cup_selection_audit": cup_audit,
        "rows": rows,
        **git_state,
    }
    summary = build_public_summary(
        config=config, rows=rows, cup_audit=cup_audit,
        git_state=git_state, output_dir=output_dir,
    )
    _write_json(output_dir / "evaluator_only_start_visibility.json", private)
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

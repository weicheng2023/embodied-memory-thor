#!/usr/bin/env python3
"""Qualify deterministic visible-and-pickupable starts for the R1 first six."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CENSUS = PROJECT_ROOT / "outputs" / "phase5_r1_scene_census_v2.json"
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
BOUNDARY = "EVALUATOR-ONLY PRIVATE START REGISTRY - NEVER PLANNER INPUT"
SCRIPT_VERSION = "phase5-r1-start-qualification-v1"


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


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


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _objects(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = metadata.get("objects", [])
    return [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []


def _book(metadata: Mapping[str, Any]) -> Mapping[str, Any] | None:
    books = sorted(
        (
            item for item in _objects(metadata)
            if item.get("objectType") == "Book" and item.get("pickupable") is True
        ),
        key=lambda item: str(item.get("objectId", "")),
    )
    return books[0] if books else None


def _normalize_pose(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    try:
        rotation = raw.get("rotation", 0.0)
        if isinstance(rotation, Mapping):
            rotation = rotation.get("y", 0.0)
        return {
            "x": float(raw["x"]),
            "y": float(raw["y"]),
            "z": float(raw["z"]),
            "rotation": float(rotation),
            "horizon": float(raw.get("horizon", raw.get("cameraHorizon", 0.0))),
            "standing": bool(raw.get("standing", True)),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _visible(metadata: Mapping[str, Any], object_id: str) -> bool:
    return any(
        item.get("objectId") == object_id and item.get("visible") is True
        for item in _objects(metadata)
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census", type=Path, default=DEFAULT_CENSUS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-pose-trials", type=int, default=32)
    args = parser.parse_args()
    if args.max_pose_trials < 1:
        raise ValueError("max-pose-trials must be positive")

    census = json.loads(args.census.resolve().read_text(encoding="utf-8"))
    scenes = list(census.get("first_six_presence_candidates", []))
    if len(scenes) != 6 or len(set(scenes)) != 6:
        raise ValueError("census must freeze exactly six distinct presence candidates")

    from ai2thor.controller import Controller

    controller = Controller(scene=scenes[0], **CONTROLLER_SETTINGS)
    rows: list[dict[str, Any]] = []
    try:
        for candidate_order, scene in enumerate(scenes, start=1):
            row: dict[str, Any] = {
                "candidate_order": candidate_order,
                "scene": scene,
                "qualified": False,
                "error": "",
            }
            try:
                reset_event = controller.reset(scene=scene)
                target = _book(reset_event.metadata)
                if target is None or not target.get("objectId"):
                    raise RuntimeError("pickupable Book unavailable after reset")
                object_id = str(target["objectId"])
                pose_event = controller.step(
                    action="GetInteractablePoses", objectId=object_id
                )
                if pose_event.metadata.get("lastActionSuccess") is not True:
                    raise RuntimeError(
                        "GetInteractablePoses failed: "
                        + str(pose_event.metadata.get("errorMessage", ""))
                    )
                raw_poses = pose_event.metadata.get("actionReturn") or []
                poses = sorted(
                    (
                        pose for pose in (
                            _normalize_pose(raw)
                            for raw in raw_poses
                            if isinstance(raw, Mapping)
                        ) if pose is not None
                    ),
                    key=lambda pose: (
                        pose["x"], pose["z"], pose["rotation"],
                        pose["horizon"], not pose["standing"], pose["y"],
                    ),
                )
                row["interactable_pose_count"] = len(poses)
                row["pose_trials"] = []
                for pose_order, pose in enumerate(poses[: args.max_pose_trials], start=1):
                    trial_reset = controller.reset(scene=scene)
                    trial_target = _book(trial_reset.metadata)
                    if trial_target is None or not trial_target.get("objectId"):
                        raise RuntimeError("Book unavailable after trial reset")
                    trial_id = str(trial_target["objectId"])
                    teleport = controller.step(action="TeleportFull", **pose)
                    teleport_success = teleport.metadata.get("lastActionSuccess") is True
                    visible = teleport_success and _visible(teleport.metadata, trial_id)
                    pickup_success = False
                    pickup_error = ""
                    if visible:
                        pickup = controller.step(action="PickupObject", objectId=trial_id)
                        pickup_success = pickup.metadata.get("lastActionSuccess") is True
                        pickup_error = str(pickup.metadata.get("errorMessage", ""))
                    trial = {
                        "pose_order": pose_order,
                        "pose": pose,
                        "pose_digest": _digest(pose),
                        "teleport_success": teleport_success,
                        "visible_after_teleport": visible,
                        "pickup_success": pickup_success,
                        "teleport_error": str(teleport.metadata.get("errorMessage", "")),
                        "pickup_error": pickup_error,
                    }
                    row["pose_trials"].append(trial)
                    if pickup_success:
                        row.update(
                            {
                                "qualified": True,
                                "target_object_id": trial_id,
                                "selected_pose": pose,
                                "selected_pose_digest": trial["pose_digest"],
                                "selected_pose_order": pose_order,
                            }
                        )
                        break
                if not row["qualified"]:
                    row["error"] = "no visible-and-pickupable pose passed within frozen trial limit"
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)
            print(
                json.dumps(
                    {
                        "candidate_order": candidate_order,
                        "scene": scene,
                        "qualified": row["qualified"],
                        "interactable_pose_count": row.get("interactable_pose_count", 0),
                        "selected_pose_order": row.get("selected_pose_order"),
                        "selected_pose_digest": row.get("selected_pose_digest"),
                        "error": row["error"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    finally:
        controller.stop()

    qualified = [row["scene"] for row in rows if row["qualified"]]
    result = {
        "qualification_version": SCRIPT_VERSION,
        "boundary": BOUNDARY,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": "visible-and-pickupable start QA; not anchor, route, task, or memory qualification",
        "source_census_digest": _digest(census),
        "runtime": {
            "ai2thor_version": _package_version("ai2thor"),
            **_git_state(),
        },
        "controller_settings": CONTROLLER_SETTINGS,
        "selection_rule": "first normalized interactable pose in xyz-rotation-horizon-standing order that passes native TeleportFull, visibility, and PickupObject",
        "max_pose_trials_per_scene": args.max_pose_trials,
        "images_saved": False,
        "memory_agents_run": False,
        "qualified_count": len(qualified),
        "all_six_start_qualified": len(qualified) == 6,
        "rows": rows,
    }
    _write_json(args.output.resolve(), result)
    print(
        "SUMMARY "
        + json.dumps(
            {
                "qualified_count": len(qualified),
                "all_six_start_qualified": len(qualified) == 6,
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if len(qualified) == 6 else 2


if __name__ == "__main__":
    raise SystemExit(main())

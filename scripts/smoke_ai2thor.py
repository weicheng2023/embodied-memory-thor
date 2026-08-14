#!/usr/bin/env python3
"""Run a reproducible live AI2-THOR integration smoke test."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """Build command-line arguments for the live simulator check."""

    parser = argparse.ArgumentParser(
        description="Start real AI2-THOR scenes and save E2 integration evidence."
    )
    parser.add_argument(
        "--scenes",
        nargs="+",
        default=["FloorPlan1", "FloorPlan10"],
        help="one or more AI2-THOR scenes",
    )
    parser.add_argument("--output-dir", help="explicit artifact directory")
    parser.add_argument("--width", type=int, default=300)
    parser.add_argument("--height", type=int, default=300)
    parser.add_argument("--quality", default="Low")
    parser.add_argument("--grid-size", type=float, default=0.25)
    parser.add_argument("--rotate-step-degrees", type=int, default=90)
    return parser


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _glx_summary() -> dict[str, str]:
    """Return the important renderer lines without failing on non-Linux hosts."""

    try:
        result = subprocess.run(
            ["glxinfo", "-B"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return {}

    wanted = (
        "direct rendering:",
        "Vendor:",
        "Device:",
        "Accelerated:",
        "OpenGL renderer string:",
        "OpenGL version string:",
    )
    summary: dict[str, str] = {}
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        for prefix in wanted:
            if line.startswith(prefix):
                summary[prefix.rstrip(":")] = line[len(prefix) :].strip()
                break
    return summary


def _visible_ids(metadata: Mapping[str, Any]) -> list[str]:
    objects = metadata.get("objects", [])
    if not isinstance(objects, list):
        return []
    return sorted(
        str(obj.get("objectId"))
        for obj in objects
        if isinstance(obj, Mapping) and obj.get("visible") and obj.get("objectId")
    )


def _interaction_candidates(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Build conservative object interactions from currently visible metadata."""

    objects = metadata.get("objects", [])
    if not isinstance(objects, list):
        return []

    candidates: list[dict[str, Any]] = []
    for obj in objects:
        if not isinstance(obj, Mapping) or not obj.get("visible"):
            continue
        object_id = obj.get("objectId")
        if not object_id:
            continue
        if obj.get("pickupable") and not obj.get("isPickedUp"):
            candidates.append({"action": "PickupObject", "objectId": object_id})
        if obj.get("openable"):
            candidates.append(
                {
                    "action": "CloseObject" if obj.get("isOpen") else "OpenObject",
                    "objectId": object_id,
                }
            )
        if obj.get("toggleable"):
            candidates.append(
                {
                    "action": "ToggleObjectOff" if obj.get("isToggled") else "ToggleObjectOn",
                    "objectId": object_id,
                }
            )
    return candidates


def _metadata_snapshot(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Keep simulator state needed for reproducible evidence, excluding pixel arrays."""

    keys = (
        "sceneName",
        "screenWidth",
        "screenHeight",
        "agent",
        "objects",
        "inventoryObjects",
        "lastAction",
        "lastActionSuccess",
        "errorMessage",
    )
    return {key: to_jsonable(metadata.get(key)) for key in keys if key in metadata}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, value: Any) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(to_jsonable(value), ensure_ascii=False, sort_keys=True) + "\n")


def _record_action(
    env: ThorEnv,
    *,
    scene: str,
    step: int,
    action: Mapping[str, Any],
    log_path: Path,
    purpose: str,
) -> dict[str, Any]:
    before = env.get_observation()
    started = perf_counter()
    event = env.step(action)
    latency = perf_counter() - started
    after = env.get_observation()
    metadata = event.metadata if isinstance(event.metadata, Mapping) else {}
    before_ids = _visible_ids(before)
    after_ids = _visible_ids(after)
    record = {
        "timestamp": _utc_now(),
        "scene": scene,
        "step": step,
        "purpose": purpose,
        "action": dict(action),
        "success": bool(metadata.get("lastActionSuccess", False)),
        "error": str(metadata.get("errorMessage", "")),
        "latency_seconds": latency,
        "agent": to_jsonable(metadata.get("agent", {})),
        "visible_object_ids_before": before_ids,
        "visible_object_ids_after": after_ids,
        "visible_added": sorted(set(after_ids) - set(before_ids)),
        "visible_removed": sorted(set(before_ids) - set(after_ids)),
    }
    _append_jsonl(log_path, record)
    return record


def _try_valid_interaction(
    env: ThorEnv,
    *,
    scene: str,
    start_step: int,
    log_path: Path,
) -> tuple[dict[str, Any] | None, int, list[dict[str, Any]]]:
    """Scan the scene and try visible, metadata-supported interactions."""

    step = start_step
    attempts: list[dict[str, Any]] = []
    tried: set[tuple[str, str]] = set()
    for scan_index in range(4):
        observation = env.get_observation()
        for action in _interaction_candidates(observation):
            key = (str(action["action"]), str(action["objectId"]))
            if key in tried:
                continue
            tried.add(key)
            step += 1
            record = _record_action(
                env,
                scene=scene,
                step=step,
                action=action,
                log_path=log_path,
                purpose="valid_object_interaction_candidate",
            )
            attempts.append(record)
            if record["success"]:
                return record, step, attempts

        if scan_index < 3:
            step += 1
            attempts.append(
                _record_action(
                    env,
                    scene=scene,
                    step=step,
                    action={"action": "RotateRight"},
                    log_path=log_path,
                    purpose="interaction_search_rotation",
                )
            )
    return None, step, attempts


def _release_cache() -> list[dict[str, Any]]:
    releases = Path.home() / ".ai2thor" / "releases"
    if not releases.is_dir():
        return []
    return [
        {
            "name": path.name,
            "path": str(path),
            "modified_at": datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
        }
        for path in sorted(releases.iterdir())
        if path.is_dir()
    ]


def _validate_args(args: argparse.Namespace) -> None:
    if args.width <= 0 or args.height <= 0:
        raise ValueError("--width and --height must be positive")
    if args.grid_size <= 0:
        raise ValueError("--grid-size must be positive")
    if args.rotate_step_degrees <= 0:
        raise ValueError("--rotate-step-degrees must be positive")
    if not args.scenes or any(not scene.strip() for scene in args.scenes):
        raise ValueError("--scenes must contain non-empty scene names")


def main(argv: list[str] | None = None) -> int:
    """Run the live smoke test and return zero only when all gates pass."""

    args = build_parser().parse_args(argv)
    try:
        _validate_args(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else PROJECT_ROOT / "outputs" / "ai2thor_smoke" / _timestamp_slug()
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    action_log_path = output_dir / "actions.jsonl"
    controller_settings = {
        "width": args.width,
        "height": args.height,
        "quality": args.quality,
        "gridSize": args.grid_size,
        "snapToGrid": True,
        "rotateStepDegrees": args.rotate_step_degrees,
        "fieldOfView": 90,
        "renderDepthImage": False,
        "renderInstanceSegmentation": False,
    }
    environment = {
        "timestamp": _utc_now(),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "wsl_distro": os.environ.get("WSL_DISTRO_NAME"),
        "ai2thor_version": _package_version("ai2thor"),
        "numpy_version": _package_version("numpy"),
        "opencv_python_version": _package_version("opencv-python"),
        "glx": _glx_summary(),
        "controller_settings": controller_settings,
        "release_cache_before": _release_cache(),
    }
    _write_json(output_dir / "environment.json", environment)

    env = ThorEnv(controller_kwargs=controller_settings)
    scene_results: list[dict[str, Any]] = []
    try:
        for scene in args.scenes:
            scene_dir = output_dir / scene
            result: dict[str, Any] = {
                "scene": scene,
                "started": False,
                "object_count": 0,
                "initial_visible_count": 0,
                "rotation_success": False,
                "movement_success": False,
                "visible_change_observed": False,
                "valid_interaction_success": False,
                "valid_interaction": None,
                "intentional_failure_observed": False,
                "frame": None,
                "error": "",
            }
            try:
                event = env.reset(scene)
                result["started"] = True
                initial_metadata = env.get_evaluator_state()
                result["object_count"] = len(initial_metadata.get("objects", []))
                result["initial_visible_count"] = len(_visible_ids(env.get_observation()))
                _write_json(
                    scene_dir / "initial_metadata.json",
                    _metadata_snapshot(initial_metadata),
                )

                step = 1
                rotation = _record_action(
                    env,
                    scene=scene,
                    step=step,
                    action={"action": "RotateRight"},
                    log_path=action_log_path,
                    purpose="required_rotation",
                )
                result["rotation_success"] = rotation["success"]

                step += 1
                movement = _record_action(
                    env,
                    scene=scene,
                    step=step,
                    action={"action": "MoveAhead"},
                    log_path=action_log_path,
                    purpose="required_movement",
                )
                result["movement_success"] = movement["success"]
                result["visible_change_observed"] = bool(
                    rotation["visible_added"]
                    or rotation["visible_removed"]
                    or movement["visible_added"]
                    or movement["visible_removed"]
                )

                interaction, step, attempts = _try_valid_interaction(
                    env,
                    scene=scene,
                    start_step=step,
                    log_path=action_log_path,
                )
                result["valid_interaction_success"] = interaction is not None
                result["valid_interaction"] = (
                    interaction["action"] if interaction is not None else None
                )
                if any(attempt["visible_added"] or attempt["visible_removed"] for attempt in attempts):
                    result["visible_change_observed"] = True

                step += 1
                failed = _record_action(
                    env,
                    scene=scene,
                    step=step,
                    action={
                        "action": "PickupObject",
                        "objectId": "__phase2_5_intentionally_missing_object__",
                    },
                    log_path=action_log_path,
                    purpose="intentional_failed_interaction",
                )
                result["intentional_failure_observed"] = not failed["success"]

                frame_path = env.save_frame(scene_dir / "rgb.png")
                result["frame"] = str(frame_path)
                _write_json(
                    scene_dir / "final_metadata.json",
                    _metadata_snapshot(env.get_evaluator_state()),
                )
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
            scene_results.append(result)
    finally:
        env.close()

    environment["release_cache_after"] = _release_cache()
    _write_json(output_dir / "environment.json", environment)

    gates = {
        "all_scenes_started": all(item["started"] for item in scene_results),
        "real_metadata_recorded": all(item["object_count"] > 0 for item in scene_results),
        "all_rotations_succeeded": all(item["rotation_success"] for item in scene_results),
        "at_least_one_movement_succeeded": any(
            item["movement_success"] for item in scene_results
        ),
        "at_least_one_valid_interaction_succeeded": any(
            item["valid_interaction_success"] for item in scene_results
        ),
        "failed_interaction_recorded": all(
            item["intentional_failure_observed"] for item in scene_results
        ),
        "visible_observation_changed": any(
            item["visible_change_observed"] for item in scene_results
        ),
        "frames_saved": all(item["frame"] for item in scene_results),
    }
    summary = {
        "evidence_level": "E2",
        "claim": "live AI2-THOR integration smoke evidence; not a memory experiment",
        "success": all(gates.values()),
        "scenes": scene_results,
        "gates": gates,
        "action_log": str(action_log_path),
        "environment": str(output_dir / "environment.json"),
        "output_dir": str(output_dir),
        "finished_at": _utc_now(),
    }
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

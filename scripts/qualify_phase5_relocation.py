#!/usr/bin/env python3
"""Run one evaluator-only real AI2-THOR Book relocation qualification probe."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.phase4.runner import THOR_BOOK_SETUP_ACTIONS  # noqa: E402
from embodied_memory_thor.phase5.qualification import (  # noqa: E402
    assess_relocation_probe,
    place_object_at_point_action,
    spawn_coordinate_query,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


PROBE_VERSION = "phase5-real-relocation-probe-v2"
OPEN_SUPPORT_TYPES = frozenset(
    {"CounterTop", "DiningTable", "CoffeeTable", "SideTable", "Desk"}
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _git_state() -> dict[str, Any]:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip())
        return {"code_revision": revision, "working_tree_dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"code_revision": "unavailable", "working_tree_dirty": None}


def _objects(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = metadata.get("objects", [])
    return [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []


def _target(metadata: Mapping[str, Any], object_id: str) -> Mapping[str, Any] | None:
    return next((obj for obj in _objects(metadata) if obj.get("objectId") == object_id), None)


def _visible_ids(metadata: Mapping[str, Any]) -> list[str]:
    return sorted(
        str(obj["objectId"])
        for obj in _objects(metadata)
        if obj.get("visible") is True and obj.get("objectId")
    )


def _xz_distance(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["z"]) - float(b["z"]))


def _run_setup(env: ThorEnv) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, action in enumerate(THOR_BOOK_SETUP_ACTIONS, start=1):
        event = env.step(action)
        metadata = event.metadata
        record = {
            "index": index,
            "action": dict(action),
            "success": bool(metadata.get("lastActionSuccess", False)),
            "error": str(metadata.get("errorMessage", "")),
        }
        records.append(record)
        if not record["success"]:
            raise RuntimeError(f"setup action failed: {record}")
    return records


def _visible_book(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    candidates = sorted(
        (
            obj for obj in _objects(metadata)
            if obj.get("objectType") == "Book"
            and obj.get("pickupable") is True
            and obj.get("visible") is True
        ),
        key=lambda obj: str(obj.get("objectId", "")),
    )
    if not candidates:
        raise RuntimeError("no visible pickupable Book after frozen setup")
    return candidates[0]


def _rank_receptacles(
    metadata: Mapping[str, Any], *, before_position: Mapping[str, Any],
    excluded_ids: Sequence[str],
) -> list[Mapping[str, Any]]:
    candidates = [
        obj for obj in _objects(metadata)
        if obj.get("receptacle") is True
        and obj.get("objectType") in OPEN_SUPPORT_TYPES
        and obj.get("objectId")
        and obj.get("objectId") not in set(excluded_ids)
        and isinstance(obj.get("position"), Mapping)
    ]
    return sorted(
        candidates,
        key=lambda obj: (
            -_xz_distance(before_position, obj["position"]),
            str(obj["objectId"]),
        ),
    )


def _query_first_spawn_surface(
    env: ThorEnv, receptacles: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any] | None, list[Mapping[str, Any]], list[dict[str, Any]]]:
    query_records: list[dict[str, Any]] = []
    for rank, receptacle in enumerate(receptacles, start=1):
        object_id = str(receptacle["objectId"])
        action = spawn_coordinate_query(object_id, anywhere=True)
        event = env.step(action)
        metadata = event.metadata
        raw = metadata.get("actionReturn")
        coordinates = [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []
        record = {
            "rank": rank,
            "receptacle_object_id": object_id,
            "receptacle_type": str(receptacle.get("objectType", "")),
            "action": action,
            "success": bool(metadata.get("lastActionSuccess", False)),
            "error": str(metadata.get("errorMessage", "")),
            "candidate_count": len(coordinates),
        }
        query_records.append(record)
        if record["success"] and coordinates:
            return receptacle, coordinates, query_records
    return None, [], query_records


def _select_destination(
    candidates: Sequence[Mapping[str, Any]], *, before_position: Mapping[str, Any],
    agent_position: Mapping[str, Any],
) -> Mapping[str, Any]:
    valid = [
        point for point in candidates
        if all(isinstance(point.get(axis), (int, float)) for axis in ("x", "y", "z"))
    ]
    if not valid:
        raise RuntimeError("spawn coordinate response has no numeric xyz point")
    return max(
        valid,
        key=lambda point: (
            min(_xz_distance(before_position, point), _xz_distance(agent_position, point)),
            _xz_distance(before_position, point),
            float(point["x"]),
            float(point["z"]),
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="FloorPlan1")
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir else PROJECT_ROOT / "outputs" / "phase5_qualification" / _slug()
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    private_path = output_dir / "evaluator_only_relocation.json"
    summary_path = output_dir / "summary.json"
    private: dict[str, Any] = {
        "probe_version": PROBE_VERSION,
        "timestamp": _utc_now(),
        "boundary": "EVALUATOR-ONLY HIDDEN STATE - NEVER PLANNER INPUT",
        "planner_visible": False,
        "included_in_planner_metrics": False,
        "scene": args.scene,
        "controller_settings": CONTROLLER_SETTINGS,
        "ai2thor_version": _package_version("ai2thor"),
        "images_saved": False,
        **_git_state(),
    }
    reasons: list[str] = []
    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    try:
        env.reset(args.scene)
        private["setup_actions"] = _run_setup(env)
        before_metadata = env.get_evaluator_state()
        book = _visible_book(before_metadata)
        object_id = str(book["objectId"])
        before_position = dict(book["position"])
        parent_ids = [str(value) for value in book.get("parentReceptacles") or []]
        agent_position = dict(before_metadata["agent"]["position"])
        private["target_before"] = {
            "objectId": object_id,
            "position": before_position,
            "visible": book.get("visible"),
            "parentReceptacles": parent_ids,
        }
        private["old_viewpoint"] = before_metadata.get("agent")

        ranked = _rank_receptacles(
            before_metadata, before_position=before_position, excluded_ids=parent_ids
        )
        private["ranked_receptacle_count"] = len(ranked)
        receptacle, spawn_candidates, query_records = _query_first_spawn_surface(env, ranked)
        private["spawn_queries"] = query_records
        if receptacle is None:
            raise RuntimeError("no ranked open support returned a valid spawn coordinate")
        destination = _select_destination(
            spawn_candidates,
            before_position=before_position,
            agent_position=agent_position,
        )
        private["selected_receptacle"] = {
            "objectId": receptacle.get("objectId"),
            "objectType": receptacle.get("objectType"),
        }
        private["selected_destination"] = dict(destination)

        placement_action = place_object_at_point_action(object_id, destination)
        placement_event = env.step(placement_action)
        placement_metadata = placement_event.metadata
        placement_success = bool(placement_metadata.get("lastActionSuccess", False))
        private["placement"] = {
            "action": placement_action,
            "success": placement_success,
            "error": str(placement_metadata.get("errorMessage", "")),
        }
        after_target = _target(placement_metadata, object_id)
        immediate_visible_ids = _visible_ids(placement_metadata)
        stability_samples: list[Mapping[str, Any]] = []
        for _ in range(2):
            sample_event = env.step({"action": "Pass"})
            sample_target = _target(sample_event.metadata, object_id)
            if sample_target is not None and isinstance(sample_target.get("position"), Mapping):
                stability_samples.append(dict(sample_target["position"]))

        assessment = assess_relocation_probe(
            target_object_id=object_id,
            before_position=before_position,
            spawn_query_success=bool(query_records[-1]["success"]),
            spawn_candidates=spawn_candidates,
            placement_success=placement_success,
            after_target=after_target,
            immediate_visible_object_ids=immediate_visible_ids,
            old_view_visible_object_ids=immediate_visible_ids,
            stability_samples=stability_samples,
        )
        private["assessment"] = assessment
        reasons.extend(assessment["rejection_reasons"])

        env.reset(args.scene)
        reset_setup = _run_setup(env)
        reset_metadata = env.get_evaluator_state()
        reset_target = _target(reset_metadata, object_id)
        reset_distance = (
            _xz_distance(before_position, reset_target["position"])
            if reset_target is not None and isinstance(reset_target.get("position"), Mapping)
            else None
        )
        reset_reproducible = (
            reset_target is not None
            and reset_target.get("visible") is True
            and reset_distance is not None
            and reset_distance <= 0.02
        )
        private["reset_check"] = {
            "setup_actions": reset_setup,
            "same_target_found": reset_target is not None,
            "target_visible": reset_target.get("visible") if reset_target else None,
            "position_delta_xz_meters": reset_distance,
            "passed": reset_reproducible,
        }
        if not reset_reproducible:
            reasons.append("scene_reset_not_reproducible")
    except Exception as exc:
        private["exception"] = f"{type(exc).__name__}: {exc}"
        reasons.append(f"probe_exception:{type(exc).__name__}")
    finally:
        env.close()

    passed = not reasons
    private["passed"] = passed
    private["rejection_reasons"] = reasons
    _write_json(private_path, private)
    summary = {
        "probe_version": PROBE_VERSION,
        "claim": "single real relocation API qualification; not a memory comparison",
        "scene": args.scene,
        "passed": passed,
        "rejection_reasons": reasons,
        "images_saved": False,
        "private_evaluator_record": str(private_path),
        "finished_at": _utc_now(),
    }
    _write_json(summary_path, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

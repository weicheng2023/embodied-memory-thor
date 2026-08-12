#!/usr/bin/env python3
"""Isolate natural settling from support-query mutation in FloorPlan202."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.phase5.qualification import (  # noqa: E402
    spawn_coordinate_query,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


SCRIPT_VERSION = "phase5-r1-support-mutation-isolation-script-v1"
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
LOGICAL_FIELDS = (
    "parentReceptacles",
    "isPickedUp",
    "isOpen",
    "isToggled",
    "isBroken",
    "isDirty",
    "isFilledWithLiquid",
)
PUBLIC_FORBIDDEN_KEYS = frozenset(
    {"objectId", "x", "y", "z", "position", "rotation", "target_point"}
)
PUBLIC_FORBIDDEN_TEXT = (
    "private_registry",
    "PlaceObjectAtPoint",
    "PickupObject",
    "forceAction",
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


def load_protocol(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("mutation isolation protocol must be an object")
    if raw.get("scene") != "FloorPlan202":
        raise ValueError("mutation isolation is restricted to FloorPlan202")
    if raw.get("isolated_query_support_types") != [
        "CoffeeTable",
        "Shelf",
        "SideTable",
    ]:
        raise ValueError("isolated query order must remain frozen")
    if raw.get("allowed_actions") != [
        "GetSpawnCoordinatesAboveReceptacle",
        "Pass",
    ]:
        raise ValueError("unexpected mutation isolation action set")
    for key in ("settling_pass_count", "baseline_followup_pass_count"):
        if not isinstance(raw.get(key), int) or raw[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    constraints = raw.get("constraints", {})
    if not isinstance(constraints, Mapping) or any(
        constraints.get(key) is not False
        for key in (
            "other_scenes_allowed",
            "placement_allowed",
            "pickup_allowed",
            "fallback_allowed",
            "memory_agents_allowed",
            "images_allowed",
            "force_action_allowed",
        )
    ):
        raise ValueError("mutation isolation constraints are not bounded")
    if constraints.get("one_receptacle_query_per_reset") is not True:
        raise ValueError("each reset must contain exactly one support query")
    return deepcopy(dict(raw))


def _objects(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = metadata.get("objects", [])
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def build_snapshot(metadata: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for obj in _objects(metadata):
        object_id = str(obj.get("objectId", ""))
        if not object_id or object_id in snapshot:
            raise ValueError("object metadata requires unique non-empty identifiers")
        snapshot[object_id] = {
            "position": deepcopy(obj.get("position")),
            "rotation": deepcopy(obj.get("rotation")),
            "parentReceptacles": deepcopy(obj.get("parentReceptacles")),
            "isMoving": obj.get("isMoving"),
            "isPickedUp": obj.get("isPickedUp"),
            "isOpen": obj.get("isOpen"),
            "isToggled": obj.get("isToggled"),
            "isBroken": obj.get("isBroken"),
            "isDirty": obj.get("isDirty"),
            "isFilledWithLiquid": obj.get("isFilledWithLiquid"),
        }
    return snapshot


def strict_snapshot_digest(snapshot: Mapping[str, Mapping[str, Any]]) -> str:
    return stable_digest(snapshot)


def logical_snapshot_digest(snapshot: Mapping[str, Mapping[str, Any]]) -> str:
    logical = {
        object_id: {field: state.get(field) for field in LOGICAL_FIELDS}
        for object_id, state in snapshot.items()
    }
    return stable_digest(logical)


def _vector(value: Any) -> dict[str, float] | None:
    if not isinstance(value, Mapping):
        return None
    try:
        result = {axis: float(value[axis]) for axis in ("x", "y", "z")}
    except (KeyError, TypeError, ValueError):
        return None
    return result if all(math.isfinite(number) for number in result.values()) else None


def compare_snapshots(
    before: Mapping[str, Mapping[str, Any]],
    after: Mapping[str, Mapping[str, Any]],
    *,
    position_threshold: float,
    rotation_threshold: float,
) -> dict[str, Any]:
    before_ids = set(before)
    after_ids = set(after)
    shared = sorted(before_ids.intersection(after_ids))
    max_position_delta = 0.0
    max_rotation_delta = 0.0
    position_changed_count = 0
    rotation_changed_count = 0
    moving_changed_count = 0
    logical_changed_object_count = 0
    logical_changed_fields: set[str] = set()
    for object_id in shared:
        left = before[object_id]
        right = after[object_id]
        left_position = _vector(left.get("position"))
        right_position = _vector(right.get("position"))
        if left_position is None or right_position is None:
            position_delta = math.inf if left_position != right_position else 0.0
        else:
            position_delta = math.sqrt(
                sum(
                    (left_position[axis] - right_position[axis]) ** 2
                    for axis in ("x", "y", "z")
                )
            )
        max_position_delta = max(max_position_delta, position_delta)
        position_changed_count += int(position_delta > 0)

        left_rotation = _vector(left.get("rotation"))
        right_rotation = _vector(right.get("rotation"))
        if left_rotation is None or right_rotation is None:
            rotation_delta = math.inf if left_rotation != right_rotation else 0.0
        else:
            rotation_delta = max(
                abs(left_rotation[axis] - right_rotation[axis])
                for axis in ("x", "y", "z")
            )
        max_rotation_delta = max(max_rotation_delta, rotation_delta)
        rotation_changed_count += int(rotation_delta > 0)
        moving_changed_count += int(left.get("isMoving") != right.get("isMoving"))
        changed_for_object = False
        for field in LOGICAL_FIELDS:
            if left.get(field) != right.get(field):
                logical_changed_fields.add(field)
                changed_for_object = True
        logical_changed_object_count += int(changed_for_object)

    exact_changed = strict_snapshot_digest(before) != strict_snapshot_digest(after)
    logical_changed = logical_snapshot_digest(before) != logical_snapshot_digest(after)
    material_change = bool(
        before_ids != after_ids
        or logical_changed
        or max_position_delta > position_threshold
        or max_rotation_delta > rotation_threshold
    )
    return {
        "strict_digest_before": strict_snapshot_digest(before),
        "strict_digest_after": strict_snapshot_digest(after),
        "logical_digest_before": logical_snapshot_digest(before),
        "logical_digest_after": logical_snapshot_digest(after),
        "strict_digest_changed": exact_changed,
        "logical_digest_changed": logical_changed,
        "material_change": material_change,
        "identity_set_changed": before_ids != after_ids,
        "object_count_before": len(before_ids),
        "object_count_after": len(after_ids),
        "position_changed_object_count": position_changed_count,
        "rotation_changed_object_count": rotation_changed_count,
        "is_moving_changed_object_count": moving_changed_count,
        "logical_changed_object_count": logical_changed_object_count,
        "logical_changed_field_categories": sorted(logical_changed_fields),
        "max_position_delta_meters": max_position_delta,
        "max_rotation_component_delta_degrees": max_rotation_delta,
        "strict_only_or_subthreshold_change": exact_changed and not material_change,
    }


def _pass_steps(env: ThorEnv, count: int) -> None:
    for _ in range(count):
        event = env.step({"action": "Pass"})
        metadata = getattr(event, "metadata", {})
        if not isinstance(metadata, Mapping) or metadata.get("lastActionSuccess") is not True:
            raise RuntimeError("Pass failed")


def _reset_and_settle(env: ThorEnv, *, scene: str, pass_count: int) -> None:
    env.reset(scene)
    _pass_steps(env, pass_count)


def _query_result(event: Any) -> tuple[bool, int, str]:
    metadata = getattr(event, "metadata", {})
    if not isinstance(metadata, Mapping):
        return False, 0, "metadata_unavailable"
    if metadata.get("lastActionSuccess") is not True:
        return False, 0, "action_failed"
    returned = metadata.get("actionReturn")
    if not isinstance(returned, list):
        return False, 0, "invalid_action_return"
    return True, len(returned), "" if returned else "empty_action_return"


def run_isolation(env: ThorEnv, protocol: Mapping[str, Any]) -> dict[str, Any]:
    scene = str(protocol["scene"])
    settling = int(protocol["settling_pass_count"])
    followup = int(protocol["baseline_followup_pass_count"])
    thresholds = protocol["material_change_thresholds"]
    comparison_args = {
        "position_threshold": float(thresholds["position_delta_meters"]),
        "rotation_threshold": float(
            thresholds["rotation_component_delta_degrees"]
        ),
    }

    _reset_and_settle(env, scene=scene, pass_count=settling)
    baseline_before = build_snapshot(env.get_evaluator_state())
    _pass_steps(env, followup)
    baseline_after = build_snapshot(env.get_evaluator_state())
    baseline = {
        "trial": "natural_settling_control",
        "query_run": False,
        "settling_pass_count": settling,
        "followup_pass_count": followup,
        "comparison": compare_snapshots(
            baseline_before, baseline_after, **comparison_args
        ),
        "reset_after_trial": True,
    }
    env.reset(scene)

    query_trials: list[dict[str, Any]] = []
    for support_type in protocol["isolated_query_support_types"]:
        _reset_and_settle(env, scene=scene, pass_count=settling)
        metadata = env.get_evaluator_state()
        supports = sorted(
            (
                obj
                for obj in _objects(metadata)
                if obj.get("objectType") == support_type
                and obj.get("receptacle") is True
            ),
            key=lambda obj: str(obj.get("objectId", "")),
        )
        if len(supports) != 1:
            raise RuntimeError(
                f"{support_type} requires exactly one receptacle for isolation"
            )
        before = build_snapshot(metadata)
        event = env.step(spawn_coordinate_query(str(supports[0]["objectId"])))
        query_success, coordinate_count, error_category = _query_result(event)
        after = build_snapshot(env.get_evaluator_state())
        trial = {
            "trial": f"isolated_{str(support_type).lower()}_query",
            "support_type": support_type,
            "query_run": True,
            "query_attempt_count": 1,
            "query_success": query_success,
            "spawn_coordinate_count": coordinate_count,
            "query_error_category": error_category,
            "comparison": compare_snapshots(before, after, **comparison_args),
            "reset_after_trial": True,
        }
        query_trials.append(trial)
        env.reset(scene)

    baseline_material = baseline["comparison"]["material_change"] is True
    query_material = [
        trial
        for trial in query_trials
        if trial["comparison"]["material_change"] is True
    ]
    any_strict_change = bool(
        baseline["comparison"]["strict_digest_changed"]
        or any(
            trial["comparison"]["strict_digest_changed"] for trial in query_trials
        )
    )
    if not baseline_material and query_material:
        classification = "case_a_query_changes_scene"
    elif baseline_material or any_strict_change:
        classification = "case_b_natural_settling_or_digest_sensitivity"
    else:
        classification = "no_state_change_detected"
    return {
        "scene": scene,
        "baseline": baseline,
        "query_trials": query_trials,
        "classification": classification,
        "material_query_support_types": [
            trial["support_type"] for trial in query_material
        ],
        "failed_query_support_types": [
            trial["support_type"]
            for trial in query_trials
            if trial["query_success"] is not True
        ],
        "all_trials_reset_isolated": True,
    }


def build_public_summary(
    *,
    protocol: Mapping[str, Any],
    result: Mapping[str, Any],
    git_state: Mapping[str, Any],
    raw_digest: str,
) -> dict[str, Any]:
    summary = {
        "protocol_version": protocol["protocol_version"],
        "script_version": SCRIPT_VERSION,
        "claim": "FloorPlan202 mutation-isolation probe; no placement, qualification, or memory comparison",
        "protocol_digest": stable_digest(protocol),
        "raw_digest": raw_digest,
        "scene": result["scene"],
        "settling_pass_count": protocol["settling_pass_count"],
        "baseline_followup_pass_count": protocol["baseline_followup_pass_count"],
        "material_change_thresholds": deepcopy(
            protocol["material_change_thresholds"]
        ),
        "baseline": deepcopy(result["baseline"]),
        "query_trials": deepcopy(result["query_trials"]),
        "classification": result["classification"],
        "material_query_support_types": list(
            result["material_query_support_types"]
        ),
        "failed_query_support_types": list(result["failed_query_support_types"]),
        "all_trials_reset_isolated": result["all_trials_reset_isolated"],
        "other_scenes_started": False,
        "placement_actions_run": False,
        "pickup_actions_run": False,
        "fallback_route_run": False,
        "memory_agents_run": False,
        "images_saved": False,
        "coordinates_exposed": False,
        **dict(git_state),
    }
    audit_public_summary(summary)
    return summary


def audit_public_summary(summary: Mapping[str, Any]) -> None:
    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            forbidden = PUBLIC_FORBIDDEN_KEYS.intersection(str(key) for key in value)
            if forbidden:
                raise ValueError(
                    f"public isolation evidence has forbidden keys: {sorted(forbidden)}"
                )
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(summary)
    serialized = json.dumps(to_jsonable(summary), sort_keys=True)
    for forbidden in PUBLIC_FORBIDDEN_TEXT:
        if forbidden in serialized:
            raise ValueError(
                f"public isolation evidence contains forbidden text: {forbidden}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            PROJECT_ROOT
            / "configs"
            / "phase5_r1_support_mutation_isolation.json"
        ),
    )
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args(argv)

    protocol = load_protocol(args.protocol.resolve())
    git_state = _git_state()
    if git_state["working_tree_dirty"] is not False:
        raise RuntimeError("clean worktree required before mutation isolation")
    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    try:
        result = run_isolation(env, protocol)
    finally:
        env.close()
    raw = {
        "protocol_version": protocol["protocol_version"],
        "script_version": SCRIPT_VERSION,
        "boundary": "EVALUATOR-ONLY MUTATION ISOLATION - NEVER PLANNER INPUT",
        "result": result,
        "other_scenes_started": False,
        "placement_actions_run": False,
        "pickup_actions_run": False,
        "fallback_route_run": False,
        "memory_agents_run": False,
        "images_saved": False,
        **git_state,
    }
    raw_digest = stable_digest(raw)
    raw["raw_digest"] = raw_digest
    summary = build_public_summary(
        protocol=protocol,
        result=result,
        git_state=git_state,
        raw_digest=raw_digest,
    )
    _write_json(args.private_output.resolve(), raw)
    _write_json(args.public_output.resolve(), summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

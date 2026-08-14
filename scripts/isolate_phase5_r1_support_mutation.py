#!/usr/bin/env python3
"""Isolate natural settling from support-query mutation in FloorPlan202."""

from __future__ import annotations

import argparse
import json
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
from embodied_memory_thor.phase5.state_audit import (  # noqa: E402
    build_object_snapshot as build_snapshot,
    circular_angle_delta as _circular_angle_delta,
    compare_object_snapshots as compare_snapshots,
    logical_snapshot_digest,
    objects_from_metadata as _objects,
    strict_snapshot_digest,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


SCRIPT_VERSION = "phase5-r1-support-mutation-isolation-script-v2"
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

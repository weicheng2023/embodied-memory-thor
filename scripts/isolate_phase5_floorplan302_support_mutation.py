#!/usr/bin/env python3
"""Run the matched-action FloorPlan302 support-query mutation isolation probe."""

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
from embodied_memory_thor.phase5.qualification import spawn_coordinate_query  # noqa: E402
from embodied_memory_thor.phase5.state_audit import (  # noqa: E402
    build_object_snapshot,
    compare_object_snapshots,
    objects_from_metadata,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


SCRIPT_VERSION = "phase5-floorplan302-support-mutation-isolation-script-v1"
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
        raise ValueError("FloorPlan302 isolation protocol must be an object")
    if raw.get("protocol_version") != (
        "phase5-floorplan302-support-mutation-isolation-v1"
    ):
        raise ValueError("unexpected FloorPlan302 isolation protocol")
    if raw.get("scene") != "FloorPlan302":
        raise ValueError("probe is restricted to FloorPlan302")
    expected_types = ["Bed", "Desk", "Shelf", "SideTable"]
    if raw.get("isolated_query_support_types") != expected_types:
        raise ValueError("FloorPlan302 support order is not frozen")
    if raw.get("expected_receptacle_counts") != {
        "Bed": 1,
        "Desk": 1,
        "Shelf": 5,
        "SideTable": 2,
    }:
        raise ValueError("FloorPlan302 receptacle counts are not frozen")
    for key in (
        "settling_pass_count",
        "control_replicate_count",
        "control_followup_pass_count",
    ):
        if not isinstance(raw.get(key), int) or raw[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    if raw.get("control_followup_pass_count") != 1:
        raise ValueError("control must contain exactly one matched followup action")
    for key in (
        "query_all_receptacles",
        "spawn_query_anywhere",
        "qualifier_query_anywhere",
        "query_parameter_alignment_with_qualifier",
    ):
        if raw.get(key) is not True:
            raise ValueError(f"{key} must be true")
    if raw.get("allowed_actions") != [
        "GetSpawnCoordinatesAboveReceptacle",
        "Pass",
    ]:
        raise ValueError("unexpected FloorPlan302 isolation action set")
    constraints = raw.get("constraints", {})
    if not isinstance(constraints, Mapping):
        raise ValueError("constraints must be an object")
    if constraints.get("one_followup_action_per_reset") is not True:
        raise ValueError("each trial must have exactly one followup action")
    for key in (
        "other_scenes_allowed",
        "placement_allowed",
        "pickup_allowed",
        "fallback_allowed",
        "memory_agents_allowed",
        "images_allowed",
        "force_action_allowed",
    ):
        if constraints.get(key) is not False:
            raise ValueError(f"constraint {key} must be false")
    return deepcopy(dict(raw))


def _pass_steps(env: ThorEnv, count: int) -> None:
    for _ in range(count):
        event = env.step({"action": "Pass"})
        metadata = getattr(event, "metadata", {})
        if not isinstance(metadata, Mapping) or metadata.get("lastActionSuccess") is not True:
            raise RuntimeError("Pass failed during FloorPlan302 isolation")


def _reset_and_settle(env: ThorEnv, *, scene: str, count: int) -> None:
    env.reset(scene)
    _pass_steps(env, count)


def _typed_receptacles(
    metadata: Mapping[str, Any], support_type: str
) -> list[dict[str, Any]]:
    return sorted(
        (
            obj
            for obj in objects_from_metadata(metadata)
            if obj.get("objectType") == support_type and obj.get("receptacle") is True
        ),
        key=lambda obj: str(obj.get("objectId", "")),
    )


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


def _control_envelope(controls: list[Mapping[str, Any]]) -> dict[str, Any]:
    comparisons = [control["comparison"] for control in controls]
    return {
        "material_control_count": sum(
            comparison["material_change"] is True for comparison in comparisons
        ),
        "logical_change_observed": any(
            comparison["logical_digest_changed"] is True
            for comparison in comparisons
        ),
        "identity_change_observed": any(
            comparison["identity_set_changed"] is True for comparison in comparisons
        ),
        "max_position_delta_meters": max(
            comparison["max_position_delta_meters"] for comparison in comparisons
        ),
        "max_rotation_component_delta_degrees": max(
            comparison["max_rotation_component_delta_degrees"]
            for comparison in comparisons
        ),
    }


def _exceeds_control_envelope(
    comparison: Mapping[str, Any], envelope: Mapping[str, Any]
) -> bool:
    return bool(
        comparison["logical_digest_changed"]
        and not envelope["logical_change_observed"]
        or comparison["identity_set_changed"]
        and not envelope["identity_change_observed"]
        or comparison["max_position_delta_meters"]
        > envelope["max_position_delta_meters"]
        or comparison["max_rotation_component_delta_degrees"]
        > envelope["max_rotation_component_delta_degrees"]
    )


def run_isolation(env: ThorEnv, protocol: Mapping[str, Any]) -> dict[str, Any]:
    scene = str(protocol["scene"])
    settling = int(protocol["settling_pass_count"])
    thresholds = protocol["material_change_thresholds"]
    comparison_args = {
        "position_threshold": float(thresholds["position_delta_meters"]),
        "rotation_threshold": float(
            thresholds["rotation_component_delta_degrees"]
        ),
    }

    _reset_and_settle(env, scene=scene, count=settling)
    initial = env.get_evaluator_state()
    for support_type, expected in protocol["expected_receptacle_counts"].items():
        actual = len(_typed_receptacles(initial, str(support_type)))
        if actual != int(expected):
            raise RuntimeError(
                f"{support_type} receptacle count changed: expected {expected}, got {actual}"
            )
    env.reset(scene)

    controls: list[dict[str, Any]] = []
    for replicate in range(1, int(protocol["control_replicate_count"]) + 1):
        _reset_and_settle(env, scene=scene, count=settling)
        before = build_object_snapshot(env.get_evaluator_state())
        _pass_steps(env, 1)
        after = build_object_snapshot(env.get_evaluator_state())
        controls.append(
            {
                "trial": "matched_pass_control",
                "replicate": replicate,
                "followup_action_count": 1,
                "comparison": compare_object_snapshots(
                    before, after, **comparison_args
                ),
                "reset_after_trial": True,
            }
        )
        env.reset(scene)

    queries: list[dict[str, Any]] = []
    for support_type in protocol["isolated_query_support_types"]:
        expected_count = int(protocol["expected_receptacle_counts"][support_type])
        for ordinal in range(expected_count):
            _reset_and_settle(env, scene=scene, count=settling)
            metadata = env.get_evaluator_state()
            receptacles = _typed_receptacles(metadata, str(support_type))
            if len(receptacles) != expected_count:
                raise RuntimeError("receptacle count changed across deterministic reset")
            before = build_object_snapshot(metadata)
            event = env.step(
                spawn_coordinate_query(
                    str(receptacles[ordinal]["objectId"]), anywhere=True
                )
            )
            success, coordinate_count, error_category = _query_result(event)
            after = build_object_snapshot(env.get_evaluator_state())
            queries.append(
                {
                    "trial": "isolated_support_query",
                    "support_type": support_type,
                    "support_ordinal": ordinal + 1,
                    "followup_action_count": 1,
                    "query_anywhere": True,
                    "query_success": success,
                    "spawn_coordinate_count": coordinate_count,
                    "query_error_category": error_category,
                    "comparison": compare_object_snapshots(
                        before, after, **comparison_args
                    ),
                    "reset_after_trial": True,
                }
            )
            env.reset(scene)

    envelope = _control_envelope(controls)
    material_queries = [
        query for query in queries if query["comparison"]["material_change"] is True
    ]
    exceeding_queries = [
        query
        for query in queries
        if _exceeds_control_envelope(query["comparison"], envelope)
    ]
    if envelope["material_control_count"] == 0 and material_queries:
        classification = "case_a_query_specific_material_change"
    elif envelope["material_control_count"] > 0 and not exceeding_queries:
        classification = "case_b_queries_within_natural_control_envelope"
    elif envelope["material_control_count"] > 0:
        classification = "mixed_material_variation_inconclusive"
    else:
        classification = "no_material_change_detected"
    return {
        "scene": scene,
        "controls": controls,
        "control_envelope": envelope,
        "query_trials": queries,
        "classification": classification,
        "material_query_trial_count": len(material_queries),
        "query_exceeding_control_envelope_count": len(exceeding_queries),
        "failed_query_trial_count": sum(
            query["query_success"] is not True for query in queries
        ),
        "all_trials_reset_isolated": True,
        "all_trials_one_followup_action": True,
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
        "claim": "FloorPlan302 matched-action mutation isolation; not placement, qualification, census selection, or memory comparison",
        "protocol_digest": stable_digest(protocol),
        "raw_digest": raw_digest,
        "scene": result["scene"],
        "settling_pass_count": protocol["settling_pass_count"],
        "control_replicate_count": protocol["control_replicate_count"],
        "spawn_query_anywhere": True,
        "query_parameter_alignment_with_qualifier": True,
        "material_change_thresholds": deepcopy(
            protocol["material_change_thresholds"]
        ),
        "controls": deepcopy(result["controls"]),
        "control_envelope": deepcopy(result["control_envelope"]),
        "query_trials": deepcopy(result["query_trials"]),
        "classification": result["classification"],
        "material_query_trial_count": result["material_query_trial_count"],
        "query_exceeding_control_envelope_count": result[
            "query_exceeding_control_envelope_count"
        ],
        "failed_query_trial_count": result["failed_query_trial_count"],
        "all_trials_reset_isolated": result["all_trials_reset_isolated"],
        "all_trials_one_followup_action": result[
            "all_trials_one_followup_action"
        ],
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
                    f"public FloorPlan302 evidence has forbidden keys: {sorted(forbidden)}"
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
                f"public FloorPlan302 evidence contains forbidden text: {forbidden}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            PROJECT_ROOT
            / "configs"
            / "phase5_floorplan302_support_mutation_isolation.json"
        ),
    )
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args(argv)

    protocol = load_protocol(args.protocol.resolve())
    git_state = _git_state()
    if git_state["working_tree_dirty"] is not False:
        raise RuntimeError("clean worktree required before FloorPlan302 isolation")
    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    try:
        result = run_isolation(env, protocol)
    finally:
        env.close()
    raw = {
        "protocol_version": protocol["protocol_version"],
        "script_version": SCRIPT_VERSION,
        "boundary": "EVALUATOR-ONLY FLOORPLAN302 ISOLATION - NEVER PLANNER INPUT",
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

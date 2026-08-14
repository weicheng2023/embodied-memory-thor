#!/usr/bin/env python3
"""Run a reset-isolated, tolerant Phase 5 R1 support census."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


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
    build_object_snapshot,
    compare_object_snapshots,
    objects_from_metadata,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


SCRIPT_VERSION = "phase5-r1-support-census-script-v2"
SCRIPT_VERSION_V3 = "phase5-r1-support-census-script-v3"
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


def load_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("census v2 config must be an object")
    expected_scenes = [
        "FloorPlan202",
        "FloorPlan301",
        "FloorPlan302",
        "FloorPlan303",
        "FloorPlan304",
        "FloorPlan305",
    ]
    expected_types = [
        "Bed",
        "CoffeeTable",
        "CounterTop",
        "Desk",
        "DiningTable",
        "Dresser",
        "Shelf",
        "SideTable",
    ]
    census_version = raw.get("census_version")
    if census_version not in {
        "phase5-r1-support-census-v2",
        "phase5-r1-support-census-v3",
    }:
        raise ValueError("unexpected census version")
    if raw.get("inspected_scenes") != expected_scenes:
        raise ValueError("census v2 scene order is not frozen")
    if raw.get("candidate_receptacle_types") != expected_types:
        raise ValueError("census v2 support type order is not frozen")
    if raw.get("one_receptacle_query_per_reset") is not True:
        raise ValueError("every receptacle query must be reset-isolated")
    query_anywhere = raw.get("spawn_query_anywhere", False)
    if not isinstance(query_anywhere, bool):
        raise ValueError("spawn_query_anywhere must be boolean")
    if census_version == "phase5-r1-support-census-v2" and query_anywhere:
        raise ValueError("historical census v2 used anywhere=false")
    if census_version == "phase5-r1-support-census-v3":
        if query_anywhere is not True:
            raise ValueError("census v3 must use anywhere=true")
        if raw.get("qualifier_query_anywhere") is not True:
            raise ValueError("qualification query contract must be explicit")
        if raw.get("query_parameter_alignment_with_qualifier") is not True:
            raise ValueError("census v3 must align with qualification")
    if not isinstance(raw.get("settling_pass_count"), int) or raw["settling_pass_count"] <= 0:
        raise ValueError("settling pass count must be positive")
    if raw.get("allowed_actions") != [
        "GetReachablePositions",
        "GetSpawnCoordinatesAboveReceptacle",
        "Pass",
    ]:
        raise ValueError("unexpected census v2 action set")
    constraints = raw.get("constraints", {})
    if not isinstance(constraints, Mapping) or any(
        constraints.get(key) is not False
        for key in (
            "placement_allowed",
            "pickup_allowed",
            "fallback_allowed",
            "memory_agents_allowed",
            "images_allowed",
            "force_action_allowed",
        )
    ):
        raise ValueError("census v2 constraints are not read-only")
    return deepcopy(dict(raw))


def _pass_steps(env: ThorEnv, count: int) -> None:
    for _ in range(count):
        event = env.step({"action": "Pass"})
        metadata = getattr(event, "metadata", {})
        if not isinstance(metadata, Mapping) or metadata.get("lastActionSuccess") is not True:
            raise RuntimeError("Pass failed during census settling")


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


def census_scene(
    env: ThorEnv,
    *,
    scene: str,
    support_types: Sequence[str],
    settling_pass_count: int,
    position_threshold: float,
    rotation_threshold: float,
    spawn_query_anywhere: bool = False,
) -> dict[str, Any]:
    _reset_and_settle(env, scene=scene, pass_count=settling_pass_count)
    initial_metadata = env.get_evaluator_state()
    initial_objects = objects_from_metadata(initial_metadata)
    pickupable_book_count = sum(
        obj.get("objectType") == "Book" and obj.get("pickupable") is True
        for obj in initial_objects
    )
    reachable_event = env.step({"action": "GetReachablePositions"})
    reachable_metadata = getattr(reachable_event, "metadata", {})
    reachable_raw = (
        reachable_metadata.get("actionReturn")
        if isinstance(reachable_metadata, Mapping)
        else None
    )
    reachable_count = len(reachable_raw) if isinstance(reachable_raw, list) else 0
    reachable_success = bool(
        isinstance(reachable_metadata, Mapping)
        and reachable_metadata.get("lastActionSuccess") is True
        and reachable_count > 0
    )

    support_rows: list[dict[str, Any]] = []
    scene_material_mutation = False
    for support_type in support_types:
        typed = [
            obj for obj in initial_objects if obj.get("objectType") == support_type
        ]
        initial_receptacles = _typed_receptacles(initial_metadata, support_type)
        query_success_count = 0
        positive_query_count = 0
        spawn_count = 0
        strict_change_count = 0
        logical_change_count = 0
        material_mutation_count = 0
        maximum_position_delta = 0.0
        maximum_rotation_delta = 0.0
        errors: Counter[str] = Counter()
        private_comparisons: list[dict[str, Any]] = []
        for ordinal in range(len(initial_receptacles)):
            _reset_and_settle(env, scene=scene, pass_count=settling_pass_count)
            metadata = env.get_evaluator_state()
            receptacles = _typed_receptacles(metadata, support_type)
            if len(receptacles) != len(initial_receptacles):
                raise RuntimeError("receptacle count changed across deterministic reset")
            before = build_object_snapshot(metadata)
            event = env.step(
                spawn_coordinate_query(
                    str(receptacles[ordinal].get("objectId", "")),
                    anywhere=spawn_query_anywhere,
                )
            )
            success, coordinate_count, error_category = _query_result(event)
            after = build_object_snapshot(env.get_evaluator_state())
            comparison = compare_object_snapshots(
                before,
                after,
                position_threshold=position_threshold,
                rotation_threshold=rotation_threshold,
            )
            query_success_count += int(success)
            positive_query_count += int(success and coordinate_count > 0)
            spawn_count += coordinate_count
            strict_change_count += int(comparison["strict_digest_changed"])
            logical_change_count += int(comparison["logical_digest_changed"])
            material_mutation_count += int(comparison["material_change"])
            maximum_position_delta = max(
                maximum_position_delta, comparison["max_position_delta_meters"]
            )
            maximum_rotation_delta = max(
                maximum_rotation_delta,
                comparison["max_rotation_component_delta_degrees"],
            )
            if error_category:
                errors[error_category] += 1
            private_comparisons.append(comparison)
            env.reset(scene)
        scene_material_mutation = scene_material_mutation or material_mutation_count > 0
        support_rows.append(
            {
                "support_type": support_type,
                "metadata_count": len(typed),
                "receptacle_true_count": len(initial_receptacles),
                "visible_receptacle_count": sum(
                    obj.get("visible") is True for obj in initial_receptacles
                ),
                "nonvisible_receptacle_count": sum(
                    obj.get("visible") is not True for obj in initial_receptacles
                ),
                "spawn_query_attempt_count": len(initial_receptacles),
                "spawn_query_success_count": query_success_count,
                "positive_spawn_query_count": positive_query_count,
                "spawn_coordinate_count": spawn_count,
                "strict_digest_changed_query_count": strict_change_count,
                "logical_digest_changed_query_count": logical_change_count,
                "material_mutation_query_count": material_mutation_count,
                "max_position_delta_meters": maximum_position_delta,
                "max_rotation_component_delta_degrees": maximum_rotation_delta,
                "error_type_summary": dict(sorted(errors.items())),
                "private_comparisons": private_comparisons,
            }
        )
    return {
        "scene": scene,
        "reset_success": True,
        "reachable_query_success": reachable_success,
        "reachable_count": reachable_count,
        "pickupable_book_count": pickupable_book_count,
        "support_types": support_rows,
        "material_mutation_detected": scene_material_mutation,
        "every_query_reset_isolated": True,
    }


def build_policy_candidate(
    config: Mapping[str, Any], scene_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    rule = config["support_policy_candidate_rule"]
    admitted: list[str] = []
    exclusions: list[dict[str, str]] = []
    for support_type in config["candidate_receptacle_types"]:
        rows = [
            next(
                row
                for row in scene["support_types"]
                if row["support_type"] == support_type
            )
            for scene in scene_rows
        ]
        presence_scenes = sum(row["receptacle_true_count"] > 0 for row in rows)
        positive_scenes = sum(row["positive_spawn_query_count"] > 0 for row in rows)
        material_mutations = sum(row["material_mutation_query_count"] for row in rows)
        if (
            presence_scenes >= int(rule["minimum_receptacle_presence_scenes"])
            and positive_scenes >= int(rule["minimum_positive_spawn_scenes"])
            and material_mutations == 0
        ):
            admitted.append(str(support_type))
        else:
            reasons: list[str] = []
            if presence_scenes < int(rule["minimum_receptacle_presence_scenes"]):
                reasons.append("too_rare_in_inspected_scenes")
            if positive_scenes < int(rule["minimum_positive_spawn_scenes"]):
                reasons.append("no_positive_reset_isolated_spawn_query")
            if material_mutations:
                reasons.append("material_query_mutation_detected")
            exclusions.append(
                {"support_type": str(support_type), "reason": "+".join(reasons)}
            )
    return {
        "policy_version": rule["policy_version"],
        "selection_rule": rule["selection_rule"],
        "admitted_support_types": admitted,
        "exclusions": exclusions,
        "placement_outcomes_used": False,
        "safety_margin_meters": rule["safety_margin_meters"],
        "route_version": rule["route_version"],
        "formal_use_allowed": False,
    }


def _public_scene(raw: Mapping[str, Any]) -> dict[str, Any]:
    public_supports: list[dict[str, Any]] = []
    for support in raw["support_types"]:
        public_supports.append(
            {
                key: deepcopy(value)
                for key, value in support.items()
                if key != "private_comparisons"
            }
        )
    return {
        "scene": raw["scene"],
        "reset_success": raw["reset_success"],
        "reachable_query_success": raw["reachable_query_success"],
        "reachable_count": raw["reachable_count"],
        "pickupable_book_count": raw["pickupable_book_count"],
        "support_types": public_supports,
        "material_mutation_detected": raw["material_mutation_detected"],
        "every_query_reset_isolated": raw["every_query_reset_isolated"],
    }


def build_public_summary(
    *,
    config: Mapping[str, Any],
    raw_scene_rows: Sequence[Mapping[str, Any]],
    git_state: Mapping[str, Any],
    raw_digest: str,
    fatal_error_category: str = "",
) -> dict[str, Any]:
    scenes = [_public_scene(row) for row in raw_scene_rows]
    aggregates: list[dict[str, Any]] = []
    for support_type in config["candidate_receptacle_types"]:
        rows = [
            next(row for row in scene["support_types"] if row["support_type"] == support_type)
            for scene in scenes
        ]
        aggregates.append(
            {
                "support_type": support_type,
                "metadata_count": sum(row["metadata_count"] for row in rows),
                "receptacle_true_count": sum(row["receptacle_true_count"] for row in rows),
                "receptacle_presence_scene_count": sum(row["receptacle_true_count"] > 0 for row in rows),
                "spawn_query_attempt_count": sum(row["spawn_query_attempt_count"] for row in rows),
                "spawn_query_success_count": sum(row["spawn_query_success_count"] for row in rows),
                "positive_spawn_scene_count": sum(row["positive_spawn_query_count"] > 0 for row in rows),
                "spawn_coordinate_count": sum(row["spawn_coordinate_count"] for row in rows),
                "material_mutation_query_count": sum(row["material_mutation_query_count"] for row in rows),
                "error_type_summary": dict(
                    sorted(
                        sum(
                            (Counter(row["error_type_summary"]) for row in rows),
                            Counter(),
                        ).items()
                    )
                ),
            }
        )
    complete = len(scenes) == len(config["inspected_scenes"])
    passed = bool(
        not fatal_error_category
        and complete
        and all(scene["reachable_query_success"] for scene in scenes)
        and all(not scene["material_mutation_detected"] for scene in scenes)
        and all(scene["every_query_reset_isolated"] for scene in scenes)
    )
    summary = {
        "census_version": config["census_version"],
        "script_version": (
            SCRIPT_VERSION_V3
            if config["census_version"] == "phase5-r1-support-census-v3"
            else SCRIPT_VERSION
        ),
        "claim": "reset-isolated tolerant support census; not placement, qualification, or memory comparison",
        "config_digest": stable_digest(config),
        "raw_digest": raw_digest,
        "inspected_scenes": list(config["inspected_scenes"]),
        "candidate_receptacle_types": list(config["candidate_receptacle_types"]),
        "material_change_thresholds": deepcopy(config["material_change_thresholds"]),
        "spawn_query_anywhere": bool(config.get("spawn_query_anywhere", False)),
        "query_parameter_alignment_with_qualifier": bool(
            config.get("query_parameter_alignment_with_qualifier", False)
        ),
        "scene_count": len(scenes),
        "census_complete": complete,
        "scenes": scenes,
        "aggregate_support_types": aggregates,
        "support_policy_candidate": build_policy_candidate(config, scenes) if complete else None,
        "support_policy_recommendation_available": passed,
        "passed": passed,
        "fatal_error_category": fatal_error_category,
        "coordinates_exposed": False,
        "placement_actions_run": False,
        "pickup_actions_run": False,
        "fallback_route_run": False,
        "memory_agents_run": False,
        "images_saved": False,
        **dict(git_state),
    }
    audit_public_summary(summary)
    return summary


def audit_public_summary(summary: Mapping[str, Any]) -> None:
    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            forbidden = PUBLIC_FORBIDDEN_KEYS.intersection(str(key) for key in value)
            if forbidden:
                raise ValueError(f"public census has forbidden keys: {sorted(forbidden)}")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(summary)
    serialized = json.dumps(to_jsonable(summary), sort_keys=True)
    for forbidden in PUBLIC_FORBIDDEN_TEXT:
        if forbidden in serialized:
            raise ValueError(f"public census contains forbidden text: {forbidden}")


def main(
    argv: list[str] | None = None, *, default_config: Path | None = None
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=(
            default_config
            if default_config is not None
            else PROJECT_ROOT / "configs" / "phase5_r1_support_census_v2.json"
        ),
    )
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args(argv)
    config = load_config(args.config.resolve())
    git_state = _git_state()
    if git_state["working_tree_dirty"] is not False:
        raise RuntimeError("clean worktree required before census v2")
    thresholds = config["material_change_thresholds"]
    raw_scene_rows: list[dict[str, Any]] = []
    fatal_error_category = ""
    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    try:
        for scene in config["inspected_scenes"]:
            try:
                row = census_scene(
                    env,
                    scene=str(scene),
                    support_types=config["candidate_receptacle_types"],
                    settling_pass_count=int(config["settling_pass_count"]),
                    position_threshold=float(thresholds["position_delta_meters"]),
                    rotation_threshold=float(thresholds["rotation_component_delta_degrees"]),
                    spawn_query_anywhere=bool(
                        config.get("spawn_query_anywhere", False)
                    ),
                )
                raw_scene_rows.append(row)
                if row["material_mutation_detected"]:
                    fatal_error_category = "material_query_mutation"
                    break
            except Exception as exc:
                fatal_error_category = type(exc).__name__
                break
    finally:
        env.close()
    raw = {
        "census_version": config["census_version"],
        "script_version": (
            SCRIPT_VERSION_V3
            if config["census_version"] == "phase5-r1-support-census-v3"
            else SCRIPT_VERSION
        ),
        "boundary": (
            f"EVALUATOR-ONLY CENSUS {config['census_version'].rsplit('-', 1)[-1].upper()}"
            " - NEVER PLANNER INPUT"
        ),
        "config_digest": stable_digest(config),
        "scenes": raw_scene_rows,
        "fatal_error_category": fatal_error_category,
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
        config=config,
        raw_scene_rows=raw_scene_rows,
        git_state=git_state,
        raw_digest=raw_digest,
        fatal_error_category=fatal_error_category,
    )
    _write_json(args.private_output.resolve(), raw)
    _write_json(args.public_output.resolve(), summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

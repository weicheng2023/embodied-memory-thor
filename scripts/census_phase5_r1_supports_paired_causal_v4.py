#!/usr/bin/env python3
"""Run the paired-causal Phase 5 R1 support census successor."""

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
from embodied_memory_thor.phase5.qualification import spawn_coordinate_query  # noqa: E402
from embodied_memory_thor.phase5.state_audit import (  # noqa: E402
    build_object_snapshot,
    compare_object_snapshots,
    compare_query_to_matched_control,
    objects_from_metadata,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


SCRIPT_VERSION = "phase5-r1-support-census-paired-causal-script-v4"
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
        raise ValueError("paired-causal census config must be an object")
    if raw.get("census_version") != "phase5-r1-support-census-paired-causal-v4":
        raise ValueError("unexpected paired-causal census version")
    if raw.get("inspected_scenes") != [
        "FloorPlan202",
        "FloorPlan301",
        "FloorPlan302",
        "FloorPlan303",
        "FloorPlan304",
        "FloorPlan305",
    ]:
        raise ValueError("paired-causal scene order is not frozen")
    if raw.get("candidate_receptacle_types") != [
        "Bed",
        "CoffeeTable",
        "CounterTop",
        "Desk",
        "DiningTable",
        "Dresser",
        "Shelf",
        "SideTable",
    ]:
        raise ValueError("paired-causal support order is not frozen")
    if raw.get("settling_pass_count") != 5:
        raise ValueError("settling pass count must remain five")
    for key in (
        "one_query_and_one_matched_pass_per_receptacle",
        "fresh_reset_per_trial",
        "spawn_query_anywhere",
        "qualifier_query_anywhere",
        "query_parameter_alignment_with_qualifier",
    ):
        if raw.get(key) is not True:
            raise ValueError(f"{key} must be true")
    if raw.get("causal_excess_thresholds") != {
        "position_delta_meters": 0.001,
        "rotation_component_delta_degrees": 0.1,
    }:
        raise ValueError("causal excess thresholds changed")
    if raw.get("allowed_actions") != [
        "GetReachablePositions",
        "GetSpawnCoordinatesAboveReceptacle",
        "Pass",
    ]:
        raise ValueError("unexpected paired-causal action set")
    constraints = raw.get("constraints", {})
    for key in (
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
            raise RuntimeError("Pass failed during paired-causal census")


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


def _run_trial(
    env: ThorEnv,
    *,
    scene: str,
    settling_pass_count: int,
    support_type: str,
    support_ordinal: int,
    expected_count: int,
    condition: str,
    absolute_diagnostic_thresholds: Mapping[str, float],
) -> dict[str, Any]:
    _reset_and_settle(env, scene=scene, count=settling_pass_count)
    metadata = env.get_evaluator_state()
    receptacles = _typed_receptacles(metadata, support_type)
    if len(receptacles) != expected_count:
        raise RuntimeError("receptacle count changed across deterministic reset")
    before = build_object_snapshot(metadata)
    if condition == "query":
        event = env.step(
            spawn_coordinate_query(
                str(receptacles[support_ordinal - 1]["objectId"]), anywhere=True
            )
        )
        query_success, coordinate_count, error_category = _query_result(event)
    elif condition == "pass":
        _pass_steps(env, 1)
        query_success, coordinate_count, error_category = True, 0, ""
    else:
        raise ValueError(f"unexpected paired-causal condition: {condition}")
    after = build_object_snapshot(env.get_evaluator_state())
    comparison = compare_object_snapshots(
        before,
        after,
        position_threshold=float(
            absolute_diagnostic_thresholds["position_delta_meters"]
        ),
        rotation_threshold=float(
            absolute_diagnostic_thresholds["rotation_component_delta_degrees"]
        ),
    )
    return {
        "condition": condition,
        "followup_action_count": 1,
        "query_anywhere": True if condition == "query" else None,
        "query_success": query_success if condition == "query" else None,
        "spawn_coordinate_count": coordinate_count,
        "query_error_category": error_category,
        "absolute_comparison_for_diagnostics_only": comparison,
        "fresh_reset_before_trial": True,
    }


def _run_pair(
    env: ThorEnv,
    *,
    scene: str,
    settling_pass_count: int,
    support_type: str,
    support_ordinal: int,
    expected_count: int,
    pair_ordinal: int,
    thresholds: Mapping[str, float],
) -> dict[str, Any]:
    order = "query_then_pass" if pair_ordinal % 2 == 1 else "pass_then_query"
    conditions = ("query", "pass") if order == "query_then_pass" else ("pass", "query")
    trials = [
        _run_trial(
            env,
            scene=scene,
            settling_pass_count=settling_pass_count,
            support_type=support_type,
            support_ordinal=support_ordinal,
            expected_count=expected_count,
            condition=condition,
            absolute_diagnostic_thresholds=thresholds,
        )
        for condition in conditions
    ]
    query = next(trial for trial in trials if trial["condition"] == "query")
    control = next(trial for trial in trials if trial["condition"] == "pass")
    causal = compare_query_to_matched_control(
        query["absolute_comparison_for_diagnostics_only"],
        control["absolute_comparison_for_diagnostics_only"],
        position_excess_threshold=float(thresholds["position_delta_meters"]),
        rotation_excess_threshold=float(
            thresholds["rotation_component_delta_degrees"]
        ),
    )
    return {
        "pair_ordinal": pair_ordinal,
        "support_type": support_type,
        "support_ordinal": support_ordinal,
        "pair_order": order,
        "query_trial": query,
        "matched_pass_control": control,
        "causal_comparison": causal,
        "pair_complete": True,
        "both_trials_fresh_reset": True,
    }


def census_scene(
    env: ThorEnv,
    *,
    scene: str,
    support_types: Sequence[str],
    settling_pass_count: int,
    thresholds: Mapping[str, float],
) -> dict[str, Any]:
    _reset_and_settle(env, scene=scene, count=settling_pass_count)
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
    pair_ordinal = 0
    stop_category = ""
    for support_type in support_types:
        typed = [
            obj for obj in initial_objects if obj.get("objectType") == support_type
        ]
        receptacles = _typed_receptacles(initial_metadata, support_type)
        pairs: list[dict[str, Any]] = []
        errors: Counter[str] = Counter()
        for support_ordinal in range(1, len(receptacles) + 1):
            pair_ordinal += 1
            pair = _run_pair(
                env,
                scene=scene,
                settling_pass_count=settling_pass_count,
                support_type=support_type,
                support_ordinal=support_ordinal,
                expected_count=len(receptacles),
                pair_ordinal=pair_ordinal,
                thresholds=thresholds,
            )
            pairs.append(pair)
            query = pair["query_trial"]
            if query["query_error_category"]:
                errors[str(query["query_error_category"])] += 1
            causal = pair["causal_comparison"]
            if causal["control_background_integrity_change"]:
                stop_category = "matched_control_background_integrity_change"
            elif causal["causal_material_query_effect"]:
                stop_category = "causal_material_query_effect"
            if stop_category:
                break
        support_rows.append(
            {
                "support_type": support_type,
                "metadata_count": len(typed),
                "receptacle_true_count": len(receptacles),
                "visible_receptacle_count": sum(
                    obj.get("visible") is True for obj in receptacles
                ),
                "nonvisible_receptacle_count": sum(
                    obj.get("visible") is not True for obj in receptacles
                ),
                "pair_count": len(pairs),
                "query_attempt_count": len(pairs),
                "query_success_count": sum(
                    pair["query_trial"]["query_success"] is True for pair in pairs
                ),
                "positive_query_count": sum(
                    pair["query_trial"]["query_success"] is True
                    and pair["query_trial"]["spawn_coordinate_count"] > 0
                    for pair in pairs
                ),
                "spawn_coordinate_count": sum(
                    pair["query_trial"]["spawn_coordinate_count"] for pair in pairs
                ),
                "causal_material_query_effect_count": sum(
                    pair["causal_comparison"]["causal_material_query_effect"] is True
                    for pair in pairs
                ),
                "background_integrity_failure_count": sum(
                    pair["causal_comparison"][
                        "control_background_integrity_change"
                    ]
                    is True
                    for pair in pairs
                ),
                "max_positive_position_excess_meters": max(
                    (
                        pair["causal_comparison"][
                            "positive_position_excess_meters"
                        ]
                        for pair in pairs
                    ),
                    default=0.0,
                ),
                "max_positive_rotation_excess_degrees": max(
                    (
                        pair["causal_comparison"][
                            "positive_rotation_excess_degrees"
                        ]
                        for pair in pairs
                    ),
                    default=0.0,
                ),
                "error_type_summary": dict(sorted(errors.items())),
                "pairs": pairs,
            }
        )
        if stop_category:
            break
    expected_pairs = sum(
        len(_typed_receptacles(initial_metadata, support_type))
        for support_type in support_types
    )
    return {
        "scene": scene,
        "reset_success": True,
        "reachable_query_success": reachable_success,
        "reachable_count": reachable_count,
        "pickupable_book_count": pickupable_book_count,
        "support_types": support_rows,
        "expected_pair_count": expected_pairs,
        "completed_pair_count": sum(row["pair_count"] for row in support_rows),
        "scene_complete": not stop_category
        and sum(row["pair_count"] for row in support_rows) == expected_pairs,
        "causal_query_effect_detected": any(
            row["causal_material_query_effect_count"] > 0 for row in support_rows
        ),
        "background_integrity_failure_detected": any(
            row["background_integrity_failure_count"] > 0 for row in support_rows
        ),
        "all_pairs_fresh_reset": all(
            pair["both_trials_fresh_reset"] is True
            for row in support_rows
            for pair in row["pairs"]
        ),
        "absolute_changes_used_for_decision": False,
        "stop_category": stop_category,
    }


def _find_support_row(
    scene: Mapping[str, Any], support_type: str
) -> Mapping[str, Any] | None:
    return next(
        (
            row
            for row in scene["support_types"]
            if row["support_type"] == support_type
        ),
        None,
    )


def build_policy_candidate(
    config: Mapping[str, Any], scenes: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    rule = config["support_policy_candidate_rule"]
    admitted: list[str] = []
    exclusions: list[dict[str, str]] = []
    for support_type in config["candidate_receptacle_types"]:
        rows = [
            row
            for scene in scenes
            if (row := _find_support_row(scene, str(support_type))) is not None
        ]
        presence_scenes = sum(row["receptacle_true_count"] > 0 for row in rows)
        positive_scenes = sum(row["positive_query_count"] > 0 for row in rows)
        causal_effects = sum(
            row["causal_material_query_effect_count"] for row in rows
        )
        background_failures = sum(
            row["background_integrity_failure_count"] for row in rows
        )
        if (
            presence_scenes >= int(rule["minimum_receptacle_presence_scenes"])
            and positive_scenes >= int(rule["minimum_positive_spawn_scenes"])
            and causal_effects == 0
            and background_failures == 0
        ):
            admitted.append(str(support_type))
        else:
            reasons: list[str] = []
            if presence_scenes < int(rule["minimum_receptacle_presence_scenes"]):
                reasons.append("too_rare_in_inspected_scenes")
            if positive_scenes < int(rule["minimum_positive_spawn_scenes"]):
                reasons.append("no_positive_paired_spawn_query")
            if causal_effects:
                reasons.append("causal_material_query_effect_detected")
            if background_failures:
                reasons.append("matched_control_background_integrity_failure")
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


def build_public_summary(
    *,
    config: Mapping[str, Any],
    scenes: Sequence[Mapping[str, Any]],
    git_state: Mapping[str, Any],
    raw_digest: str,
    fatal_error_category: str = "",
) -> dict[str, Any]:
    complete = len(scenes) == len(config["inspected_scenes"]) and all(
        scene["scene_complete"] for scene in scenes
    )
    passed = bool(
        not fatal_error_category
        and complete
        and all(scene["reachable_query_success"] for scene in scenes)
        and all(not scene["causal_query_effect_detected"] for scene in scenes)
        and all(
            not scene["background_integrity_failure_detected"] for scene in scenes
        )
        and all(scene["all_pairs_fresh_reset"] for scene in scenes)
        and all(not scene["absolute_changes_used_for_decision"] for scene in scenes)
    )
    aggregates: list[dict[str, Any]] = []
    for support_type in config["candidate_receptacle_types"]:
        rows = [
            row
            for scene in scenes
            if (row := _find_support_row(scene, str(support_type))) is not None
        ]
        aggregates.append(
            {
                "support_type": support_type,
                "metadata_count": sum(row["metadata_count"] for row in rows),
                "receptacle_true_count": sum(
                    row["receptacle_true_count"] for row in rows
                ),
                "receptacle_presence_scene_count": sum(
                    row["receptacle_true_count"] > 0 for row in rows
                ),
                "pair_count": sum(row["pair_count"] for row in rows),
                "query_success_count": sum(
                    row["query_success_count"] for row in rows
                ),
                "positive_spawn_scene_count": sum(
                    row["positive_query_count"] > 0 for row in rows
                ),
                "spawn_coordinate_count": sum(
                    row["spawn_coordinate_count"] for row in rows
                ),
                "causal_material_query_effect_count": sum(
                    row["causal_material_query_effect_count"] for row in rows
                ),
                "background_integrity_failure_count": sum(
                    row["background_integrity_failure_count"] for row in rows
                ),
                "max_positive_position_excess_meters": max(
                    (row["max_positive_position_excess_meters"] for row in rows),
                    default=0.0,
                ),
                "max_positive_rotation_excess_degrees": max(
                    (row["max_positive_rotation_excess_degrees"] for row in rows),
                    default=0.0,
                ),
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
    summary = {
        "census_version": config["census_version"],
        "script_version": SCRIPT_VERSION,
        "claim": "paired-causal support census; every support query is compared only against a fresh-reset matched Pass control",
        "config_digest": stable_digest(config),
        "raw_digest": raw_digest,
        "inspected_scenes": list(config["inspected_scenes"]),
        "candidate_receptacle_types": list(config["candidate_receptacle_types"]),
        "causal_excess_thresholds": deepcopy(config["causal_excess_thresholds"]),
        "spawn_query_anywhere": True,
        "query_parameter_alignment_with_qualifier": True,
        "scene_count": len(scenes),
        "census_complete": complete,
        "scenes": deepcopy(list(scenes)),
        "aggregate_support_types": aggregates,
        "support_policy_candidate": build_policy_candidate(config, scenes)
        if complete
        else None,
        "support_policy_recommendation_available": passed,
        "passed": passed,
        "fatal_error_category": fatal_error_category,
        "absolute_one_action_pose_changes_used_for_decision": False,
        "every_support_query_has_matched_pass": all(
            scene["completed_pair_count"] == scene["expected_pair_count"]
            for scene in scenes
        ),
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
                raise ValueError(
                    f"public paired-causal census has forbidden keys: {sorted(forbidden)}"
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
                f"public paired-causal census contains forbidden text: {forbidden}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=(
            PROJECT_ROOT
            / "configs"
            / "phase5_r1_support_census_paired_causal_v4.json"
        ),
    )
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args(argv)

    config = load_config(args.config.resolve())
    git_state = _git_state()
    if git_state["working_tree_dirty"] is not False:
        raise RuntimeError("clean worktree required before paired-causal census")
    scenes: list[dict[str, Any]] = []
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
                    thresholds=config["causal_excess_thresholds"],
                )
                scenes.append(row)
                if row["stop_category"]:
                    fatal_error_category = str(row["stop_category"])
                    break
            except Exception as exc:
                fatal_error_category = type(exc).__name__
                break
    finally:
        env.close()
    raw = {
        "census_version": config["census_version"],
        "script_version": SCRIPT_VERSION,
        "boundary": "EVALUATOR-ONLY PAIRED-CAUSAL CENSUS - NEVER PLANNER INPUT",
        "config_digest": stable_digest(config),
        "scenes": scenes,
        "fatal_error_category": fatal_error_category,
        "absolute_one_action_pose_changes_used_for_decision": False,
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
        scenes=scenes,
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

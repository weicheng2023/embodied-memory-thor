#!/usr/bin/env python3
"""Run the counterbalanced FloorPlan302 Shelf-4 paired attribution probe."""

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
from embodied_memory_thor.phase5.paired_attribution import (  # noqa: E402
    classify_paired_attribution,
    paired_mean_interval,
)
from embodied_memory_thor.phase5.qualification import spawn_coordinate_query  # noqa: E402
from embodied_memory_thor.phase5.state_audit import (  # noqa: E402
    build_object_snapshot,
    compare_object_snapshots,
    objects_from_metadata,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


SCRIPT_VERSION = "phase5-floorplan302-shelf4-paired-attribution-script-v1"
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
        raise ValueError("paired attribution protocol must be an object")
    if raw.get("protocol_version") != (
        "phase5-floorplan302-shelf4-paired-attribution-v1"
    ):
        raise ValueError("unexpected paired attribution protocol")
    if raw.get("scene") != "FloorPlan302":
        raise ValueError("paired attribution is FloorPlan302-only")
    if raw.get("target_support_type") != "Shelf":
        raise ValueError("target support type must remain Shelf")
    if raw.get("target_support_ordinal") != 4:
        raise ValueError("target support ordinal must remain 4")
    if raw.get("expected_target_support_count") != 5:
        raise ValueError("expected Shelf count must remain 5")
    if raw.get("pair_count") != 12:
        raise ValueError("paired design must contain 12 pairs")
    expected_orders = [
        "query_then_pass" if index % 2 == 0 else "pass_then_query"
        for index in range(12)
    ]
    if raw.get("pair_orders") != expected_orders:
        raise ValueError("pair orders must use frozen balanced AB/BA order")
    if raw.get("settling_pass_count") != 5:
        raise ValueError("settling pass count must remain five")
    for key in (
        "spawn_query_anywhere",
        "qualifier_query_anywhere",
        "query_parameter_alignment_with_qualifier",
    ):
        if raw.get(key) is not True:
            raise ValueError(f"{key} must be true")
    endpoints = raw.get("continuous_endpoints", {})
    if endpoints != {
        "max_rotation_component_delta_degrees": {"practical_margin": 0.1},
        "max_position_delta_meters": {"practical_margin": 0.001},
    }:
        raise ValueError("continuous endpoints or practical margins changed")
    statistics = raw.get("statistics", {})
    if statistics != {
        "familywise_alpha": 0.05,
        "continuous_endpoint_count": 2,
        "per_endpoint_one_sided_alpha": 0.025,
        "confidence_level": 0.975,
        "degrees_of_freedom": 11,
        "t_critical": 2.200985160082949,
    }:
        raise ValueError("paired statistics contract changed")
    if raw.get("allowed_actions") != [
        "GetSpawnCoordinatesAboveReceptacle",
        "Pass",
    ]:
        raise ValueError("unexpected paired attribution action set")
    constraints = raw.get("constraints", {})
    if constraints.get("one_followup_action_per_reset") is not True:
        raise ValueError("each reset must have one measured followup action")
    for key in (
        "other_scenes_allowed",
        "placement_allowed",
        "pickup_allowed",
        "fallback_allowed",
        "memory_agents_allowed",
        "images_allowed",
        "force_action_allowed",
        "census_v3_allowed",
    ):
        if constraints.get(key) is not False:
            raise ValueError(f"constraint {key} must be false")
    return deepcopy(dict(raw))


def _pass_steps(env: ThorEnv, count: int) -> None:
    for _ in range(count):
        event = env.step({"action": "Pass"})
        metadata = getattr(event, "metadata", {})
        if not isinstance(metadata, Mapping) or metadata.get("lastActionSuccess") is not True:
            raise RuntimeError("Pass failed during paired attribution")


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
    protocol: Mapping[str, Any],
    pair: int,
    period: int,
    condition: str,
) -> dict[str, Any]:
    scene = str(protocol["scene"])
    settling = int(protocol["settling_pass_count"])
    _reset_and_settle(env, scene=scene, count=settling)
    metadata = env.get_evaluator_state()
    supports = _typed_receptacles(metadata, str(protocol["target_support_type"]))
    if len(supports) != int(protocol["expected_target_support_count"]):
        raise RuntimeError("Shelf count changed across deterministic reset")
    before = build_object_snapshot(metadata)
    if condition == "query":
        target = supports[int(protocol["target_support_ordinal"]) - 1]
        event = env.step(
            spawn_coordinate_query(str(target["objectId"]), anywhere=True)
        )
        query_success, coordinate_count, error_category = _query_result(event)
    elif condition == "pass":
        _pass_steps(env, 1)
        query_success, coordinate_count, error_category = True, 0, ""
    else:
        raise ValueError(f"unexpected trial condition: {condition}")
    after = build_object_snapshot(env.get_evaluator_state())
    thresholds = protocol["continuous_endpoints"]
    comparison = compare_object_snapshots(
        before,
        after,
        position_threshold=float(
            thresholds["max_position_delta_meters"]["practical_margin"]
        ),
        rotation_threshold=float(
            thresholds["max_rotation_component_delta_degrees"][
                "practical_margin"
            ]
        ),
    )
    env.reset(scene)
    return {
        "pair": pair,
        "period": period,
        "condition": condition,
        "followup_action_count": 1,
        "query_anywhere": True if condition == "query" else None,
        "query_success": query_success if condition == "query" else None,
        "spawn_coordinate_count": coordinate_count,
        "query_error_category": error_category,
        "comparison": comparison,
        "reset_after_trial": True,
    }


def analyze_trials(
    trials: list[Mapping[str, Any]], protocol: Mapping[str, Any]
) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    for pair_number in range(1, int(protocol["pair_count"]) + 1):
        rows = [row for row in trials if row["pair"] == pair_number]
        if len(rows) != 2 or {row["condition"] for row in rows} != {"query", "pass"}:
            raise ValueError("each pair must contain one query and one Pass")
        query = next(row for row in rows if row["condition"] == "query")
        control = next(row for row in rows if row["condition"] == "pass")
        pairs.append({"pair": pair_number, "query": query, "control": control})

    endpoints = protocol["continuous_endpoints"]
    t_critical = float(protocol["statistics"]["t_critical"])
    intervals: dict[str, dict[str, Any]] = {}
    for endpoint in endpoints:
        intervals[endpoint] = paired_mean_interval(
            [pair["query"]["comparison"][endpoint] for pair in pairs],
            [pair["control"]["comparison"][endpoint] for pair in pairs],
            t_critical=t_critical,
        )
    control_logical = sum(
        pair["control"]["comparison"]["logical_digest_changed"] is True
        for pair in pairs
    )
    control_identity = sum(
        pair["control"]["comparison"]["identity_set_changed"] is True
        for pair in pairs
    )
    query_logical = sum(
        pair["query"]["comparison"]["logical_digest_changed"] is True
        for pair in pairs
    )
    query_identity = sum(
        pair["query"]["comparison"]["identity_set_changed"] is True
        for pair in pairs
    )
    failed_queries = sum(
        pair["query"]["query_success"] is not True for pair in pairs
    )
    classification = classify_paired_attribution(
        endpoint_intervals=intervals,
        practical_margins={
            endpoint: float(spec["practical_margin"])
            for endpoint, spec in endpoints.items()
        },
        control_logical_change_count=control_logical,
        control_identity_change_count=control_identity,
        query_logical_change_count=query_logical,
        query_identity_change_count=query_identity,
        failed_query_count=failed_queries,
    )
    return {
        "pairs": pairs,
        "endpoint_intervals": intervals,
        "classification": classification["classification"],
        "effect_endpoints": classification["effect_endpoints"],
        "below_margin_endpoints": classification["below_margin_endpoints"],
        "failed_query_count": failed_queries,
        "control_logical_change_count": control_logical,
        "control_identity_change_count": control_identity,
        "query_logical_change_count": query_logical,
        "query_identity_change_count": query_identity,
    }


def run_probe(env: ThorEnv, protocol: Mapping[str, Any]) -> dict[str, Any]:
    trials: list[dict[str, Any]] = []
    for pair, order in enumerate(protocol["pair_orders"], start=1):
        conditions = (
            ("query", "pass")
            if order == "query_then_pass"
            else ("pass", "query")
        )
        for period, condition in enumerate(conditions, start=1):
            trials.append(
                _run_trial(
                    env,
                    protocol=protocol,
                    pair=pair,
                    period=period,
                    condition=condition,
                )
            )
    analysis = analyze_trials(trials, protocol)
    return {
        "scene": protocol["scene"],
        "target_support_type": protocol["target_support_type"],
        "target_support_ordinal": protocol["target_support_ordinal"],
        "trials": trials,
        **analysis,
        "all_trials_reset_isolated": True,
        "all_trials_one_followup_action": True,
        "balanced_order": protocol["pair_orders"].count("query_then_pass")
        == protocol["pair_orders"].count("pass_then_query"),
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
        "claim_scope": protocol["claim_scope"],
        "protocol_digest": stable_digest(protocol),
        "raw_digest": raw_digest,
        "scene": result["scene"],
        "target_support_type": result["target_support_type"],
        "target_support_ordinal": result["target_support_ordinal"],
        "settling_pass_count": protocol["settling_pass_count"],
        "pair_count": protocol["pair_count"],
        "pair_orders": list(protocol["pair_orders"]),
        "spawn_query_anywhere": True,
        "query_parameter_alignment_with_qualifier": True,
        "continuous_endpoints": deepcopy(protocol["continuous_endpoints"]),
        "statistics": deepcopy(protocol["statistics"]),
        "trials": deepcopy(result["trials"]),
        "endpoint_intervals": deepcopy(result["endpoint_intervals"]),
        "classification": result["classification"],
        "effect_endpoints": list(result["effect_endpoints"]),
        "below_margin_endpoints": list(result["below_margin_endpoints"]),
        "failed_query_count": result["failed_query_count"],
        "control_logical_change_count": result["control_logical_change_count"],
        "control_identity_change_count": result["control_identity_change_count"],
        "query_logical_change_count": result["query_logical_change_count"],
        "query_identity_change_count": result["query_identity_change_count"],
        "all_trials_reset_isolated": result["all_trials_reset_isolated"],
        "all_trials_one_followup_action": result[
            "all_trials_one_followup_action"
        ],
        "balanced_order": result["balanced_order"],
        "other_scenes_started": False,
        "placement_actions_run": False,
        "pickup_actions_run": False,
        "fallback_route_run": False,
        "memory_agents_run": False,
        "images_saved": False,
        "census_v3_run": False,
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
                    f"public paired evidence has forbidden keys: {sorted(forbidden)}"
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
                f"public paired evidence contains forbidden text: {forbidden}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            PROJECT_ROOT
            / "configs"
            / "phase5_floorplan302_shelf4_paired_attribution.json"
        ),
    )
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args(argv)

    protocol = load_protocol(args.protocol.resolve())
    git_state = _git_state()
    if git_state["working_tree_dirty"] is not False:
        raise RuntimeError("clean worktree required before paired attribution")
    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    try:
        result = run_probe(env, protocol)
    finally:
        env.close()
    raw = {
        "protocol_version": protocol["protocol_version"],
        "script_version": SCRIPT_VERSION,
        "boundary": "EVALUATOR-ONLY PAIRED ATTRIBUTION - NEVER PLANNER INPUT",
        "result": result,
        "other_scenes_started": False,
        "placement_actions_run": False,
        "pickup_actions_run": False,
        "fallback_route_run": False,
        "memory_agents_run": False,
        "images_saved": False,
        "census_v3_run": False,
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

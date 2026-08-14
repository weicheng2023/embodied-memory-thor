#!/usr/bin/env python3
"""Run the fixed-N independent FloorPlan302 Shelf-4 replication cohort."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import probe_phase5_floorplan302_shelf4_paired_attribution as paired  # noqa: E402


SCRIPT_VERSION = "phase5-floorplan302-shelf4-independent-replication-script-v1"
PROTOCOL_VERSION = "phase5-floorplan302-shelf4-independent-replication-v1"


def load_protocol(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("independent replication protocol must be an object")
    if raw.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("unexpected independent replication protocol")
    if raw.get("scene") != "FloorPlan302":
        raise ValueError("independent replication is FloorPlan302-only")
    if raw.get("target_support_type") != "Shelf":
        raise ValueError("target support type must remain Shelf")
    if raw.get("target_support_ordinal") != 4:
        raise ValueError("target support ordinal must remain 4")
    if raw.get("expected_target_support_count") != 5:
        raise ValueError("expected Shelf count must remain five")
    if raw.get("settling_pass_count") != 5:
        raise ValueError("settling pass count must remain five")
    if raw.get("pair_count") != 24:
        raise ValueError("independent replication must contain 24 pairs")
    expected_orders = [
        "query_then_pass" if index % 2 == 0 else "pass_then_query"
        for index in range(24)
    ]
    if raw.get("pair_orders") != expected_orders:
        raise ValueError("replication pair order must remain balanced and frozen")
    for key in (
        "spawn_query_anywhere",
        "qualifier_query_anywhere",
        "query_parameter_alignment_with_qualifier",
    ):
        if raw.get(key) is not True:
            raise ValueError(f"{key} must be true")
    if raw.get("continuous_endpoints") != {
        "max_rotation_component_delta_degrees": {"practical_margin": 0.1},
        "max_position_delta_meters": {"practical_margin": 0.001},
    }:
        raise ValueError("replication endpoints or margins changed")
    if raw.get("statistics") != {
        "familywise_alpha": 0.05,
        "continuous_endpoint_count": 2,
        "per_endpoint_one_sided_alpha": 0.025,
        "confidence_level": 0.975,
        "degrees_of_freedom": 23,
        "t_critical": 2.068657610419041,
    }:
        raise ValueError("replication statistical contract changed")
    prior = raw.get("prior_cohort", {})
    if prior.get("used_for_sample_size_planning") is not True:
        raise ValueError("prior planning use must be explicit")
    if prior.get("used_for_decision") is not False:
        raise ValueError("prior cohort cannot enter replication decision")
    if prior.get("pooled_with_replication") is not False:
        raise ValueError("prior and replication cohorts cannot be pooled")
    execution = raw.get("execution_policy", {})
    if execution != {
        "fixed_pair_count": True,
        "interim_analysis_allowed": False,
        "interim_output_allowed": False,
        "optional_sample_extension_allowed": False,
        "write_outputs_only_after_all_trials": True,
    }:
        raise ValueError("no-peeking replication execution policy changed")
    if raw.get("allowed_actions") != [
        "GetSpawnCoordinatesAboveReceptacle",
        "Pass",
    ]:
        raise ValueError("unexpected replication action set")
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
        "census_v3_allowed_during_probe",
    ):
        if constraints.get(key) is not False:
            raise ValueError(f"constraint {key} must be false")
    return deepcopy(dict(raw))


def build_public_summary(
    *,
    protocol: Mapping[str, Any],
    result: Mapping[str, Any],
    git_state: Mapping[str, Any],
    raw_digest: str,
) -> dict[str, Any]:
    summary = paired.build_public_summary(
        protocol=protocol,
        result=result,
        git_state=git_state,
        raw_digest=raw_digest,
    )
    summary.update(
        {
            "script_version": SCRIPT_VERSION,
            "cohort_role": "independent_replication",
            "decision_data": "replication_cohort_only",
            "prior_cohort_used_for_sample_size_planning": True,
            "prior_cohort_used_for_decision": False,
            "prior_cohort_pooled_with_replication": False,
            "fixed_pair_count": True,
            "interim_analysis_run": False,
            "interim_output_written": False,
            "optional_sample_extension_allowed": False,
            "census_v3_review_eligible": result["classification"]
            == "no_material_query_effect_supported",
            "census_v3_run": False,
        }
    )
    paired.audit_public_summary(summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            PROJECT_ROOT
            / "configs"
            / "phase5_floorplan302_shelf4_independent_replication.json"
        ),
    )
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args(argv)

    protocol = load_protocol(args.protocol.resolve())
    git_state = paired._git_state()
    if git_state["working_tree_dirty"] is not False:
        raise RuntimeError("clean worktree required before independent replication")
    env = paired.ThorEnv(controller_kwargs=paired.CONTROLLER_SETTINGS)
    try:
        result = paired.run_probe(env, protocol)
    finally:
        env.close()

    # No output is written and no analysis is exposed until the full fixed-N
    # cohort above has completed in memory.
    raw = {
        "protocol_version": protocol["protocol_version"],
        "script_version": SCRIPT_VERSION,
        "boundary": "EVALUATOR-ONLY INDEPENDENT REPLICATION - NEVER PLANNER INPUT",
        "cohort_role": "independent_replication",
        "decision_data": "replication_cohort_only",
        "result": result,
        "prior_cohort_used_for_decision": False,
        "prior_cohort_pooled_with_replication": False,
        "interim_analysis_run": False,
        "interim_output_written": False,
        "other_scenes_started": False,
        "placement_actions_run": False,
        "pickup_actions_run": False,
        "fallback_route_run": False,
        "memory_agents_run": False,
        "images_saved": False,
        "census_v3_run": False,
        **git_state,
    }
    raw_digest = paired.stable_digest(raw)
    raw["raw_digest"] = raw_digest
    summary = build_public_summary(
        protocol=protocol,
        result=result,
        git_state=git_state,
        raw_digest=raw_digest,
    )
    paired._write_json(args.private_output.resolve(), raw)
    paired._write_json(args.public_output.resolve(), summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

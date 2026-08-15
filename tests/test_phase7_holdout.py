from __future__ import annotations

import json
import importlib.util
import hashlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase4.task import BookReacquireProgress
from embodied_memory_thor.phase5.search import FrozenSearchRoute
from embodied_memory_thor.phase5.anchors import stable_digest
from embodied_memory_thor.phase7.holdout import (
    PHASE7A_GENERIC_ROUTE_POLICY_VERSION,
    PHASE7A_ROUTE_ACTION_LIMIT,
    PHASE7A_VARIANTS,
    Phase7AHoldoutError,
    build_phase7a_generic_route,
    build_public_route_contract,
    distraction_actions_for_horizon,
    load_phase7a_holdout_runtime,
    normalize_interactable_pose,
    validate_public_artifact,
)

def _grid(width: int, depth: int) -> list[dict[str, float]]:
    return [
        {"x": x * 0.25, "y": 0.9, "z": z * 0.25}
        for x in range(width)
        for z in range(depth)
    ]


def test_candidate_pool_excludes_phase5_formal_scenes_and_is_deterministic() -> None:
    pool = json.loads(
        (ROOT / "configs" / "phase7" / "holdout_candidate_pool.json").read_text(
            encoding="utf-8"
        )
    )
    candidates = pool["ordered_candidates"]
    assert len(candidates) == len(set(candidates)) == 21
    assert candidates == sorted(candidates, key=lambda value: int(value[9:]))
    assert not set(candidates) & set(pool["excluded_phase5_formal_scenes"])
    assert pool["target_configuration_count"] == 6


def test_preregistered_manifest_freezes_variants_and_budgets() -> None:
    manifest = json.loads(
        (ROOT / "configs" / "phase7" / "holdout_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert tuple(manifest["variants"]) == PHASE7A_VARIANTS
    assert manifest["success_budgets"] == [18, 72, 2048]
    assert manifest["route_action_limit"] == PHASE7A_ROUTE_ACTION_LIMIT
    assert manifest["optional_ai_planner_used"] is False
    assert manifest["status"] == "preregistered_no_outcomes"


@pytest.mark.parametrize("horizon", [-30.0, 0.0, 30.0, 60.0])
def test_distraction_template_matches_phase5_v4(horizon: float) -> None:
    progress = BookReacquireProgress.phase5_k2_v4()
    progress.initialize(
        {
            "agent": {"cameraHorizon": horizon},
            "objects": [
                {
                    "objectId": "Book|fixture",
                    "objectType": "Book",
                    "pickupable": True,
                    "visible": True,
                }
            ],
        }
    )
    assert tuple(progress.distraction_actions) == distraction_actions_for_horizon(
        horizon
    )


def test_generic_route_is_deterministic_target_free_and_bounded() -> None:
    kwargs = {
        "reachable_positions": _grid(7, 5),
        "start_pose": {
            "x": 0.0,
            "y": 0.9,
            "z": 0.0,
            "rotation": 90.0,
            "horizon": 30.0,
            "standing": True,
        },
    }
    first = build_phase7a_generic_route(**kwargs)
    second = build_phase7a_generic_route(**kwargs)
    assert first == second
    assert first["route_version"] == PHASE7A_GENERIC_ROUTE_POLICY_VERSION
    assert first["target_or_anchor_input_used"] is False
    assert first["memory_input_used"] is False
    assert first["memory_variant_input_used"] is False
    assert first["candidate_outcome_input_used"] is False
    assert first["action_count"] <= PHASE7A_ROUTE_ACTION_LIMIT

    contract = build_public_route_contract(
        scene="FloorPlan999",
        configuration_id="FloorPlan999_Phase7A_R1_001",
        route=first,
    )
    route = FrozenSearchRoute(
        route_id=contract["route_id"],
        task=contract["task"],
        scene=contract["scene"],
        source_qualification_route_digest=contract[
            "source_qualification_route_digest"
        ],
        action_sequence_digest=contract["action_sequence_digest"],
        action_codes=contract["action_codes"],
        route_role=contract["route_role"],
        qualification_goal_input_used=False,
        target_or_anchor_input_used=False,
    )
    route.validate()


def test_public_artifact_guard_rejects_hidden_fields() -> None:
    validate_public_artifact({"scene": "FloorPlan308", "action_count": 10})
    with pytest.raises(Phase7AHoldoutError, match="target_object_id"):
        validate_public_artifact({"target_object_id": "Book|secret"})
    with pytest.raises(Phase7AHoldoutError, match="reachable_positions"):
        validate_public_artifact({"nested": {"reachable_positions": []}})


def test_matrix_loader_keeps_evaluator_setup_out_of_public_reference(
    tmp_path: Path,
) -> None:
    pose = {
        "x": 0.0,
        "y": 0.9,
        "z": 0.0,
        "rotation": 0.0,
        "horizon": 0.0,
        "standing": True,
    }
    route = build_phase7a_generic_route(
        reachable_positions=_grid(2, 2), start_pose=pose
    )
    configuration_id = "FloorPlan999_Phase7A_R1_holdout_001"
    route_contract = build_public_route_contract(
        scene="FloorPlan999",
        configuration_id=configuration_id,
        route=route,
    )
    routes_path = tmp_path / "routes.json"
    routes_path.write_text(
        json.dumps(
            {"schema_version": "phase5-search-route-v1", "routes": [route_contract]},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    private = {
        "registry_version": "phase7a-holdout-evaluator-registry-v1",
        "boundary": "EVALUATOR-ONLY PHASE7A HOLDOUT SETUP - NEVER PLANNER INPUT",
        "planner_visible": False,
        "included_in_planner_metrics": False,
        "configuration_count": 1,
        "configurations": [
            {
                "configuration_id": configuration_id,
                "scene": "FloorPlan999",
                "target_object_id": "Book|secret",
                "start_action": {"action": "TeleportFull", **pose},
                "start_pose_digest": stable_digest(pose),
                "route_id": route_contract["route_id"],
            }
        ],
    }
    private["private_registry_digest"] = stable_digest(private)
    private_path = tmp_path / "private.json"
    private_path.write_text(
        json.dumps(private, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "status": "matrix_frozen_no_outcomes",
        "private_registry_digest": private["private_registry_digest"],
        "evaluator_registry_sha256": hashlib.sha256(
            private_path.read_bytes()
        ).hexdigest(),
        "route_registry_sha256": hashlib.sha256(routes_path.read_bytes()).hexdigest(),
        "selected_configurations": [
            {
                "configuration_id": configuration_id,
                "scene": "FloorPlan999",
                "start_pose_digest": stable_digest(pose),
                "route_id": route_contract["route_id"],
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    runtime = load_phase7a_holdout_runtime(
        configuration_id,
        manifest_path=manifest_path,
        private_registry_path=private_path,
        route_registry_path=routes_path,
    )
    public = runtime.configuration.public_reference()
    assert public["planner_visible"] is False
    assert "target_object_id" not in public
    assert "start_action" not in public


def test_pose_normalization_is_absolute_horizon_safe() -> None:
    assert normalize_interactable_pose(
        {
            "x": 1,
            "y": 0.9,
            "z": -2,
            "rotation": {"y": 450},
            "horizon": 60.000015,
            "standing": True,
        }
    ) == {
        "x": 1.0,
        "y": 0.9,
        "z": -2.0,
        "rotation": 90.0,
        "horizon": 60.0,
        "standing": True,
    }


def test_holdout_result_row_uses_frozen_success_budgets() -> None:
    script = ROOT / "scripts" / "phase7" / "run_holdout.py"
    spec = importlib.util.spec_from_file_location("phase7a_run_holdout", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    summary = {
        "scene": "FloorPlan308",
        "memory": "object_memory",
        "success": True,
        "failure_reason": "",
        "steps": 20,
    }
    row = module.compact_result_row(
        episode_index=1,
        configuration_id="FloorPlan308_Phase7A_R1_holdout_001",
        summary=summary,
        integrity_errors=[],
        budgets=[18, 72, 2048],
    )
    assert row["success_at_18"] is False
    assert row["success_at_72"] is True
    assert row["success_at_2048"] is True


def test_holdout_aggregator_requires_fresh_ordered_triplets() -> None:
    script = ROOT / "scripts" / "phase7" / "aggregate_holdout.py"
    spec = importlib.util.spec_from_file_location("phase7a_aggregate", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for configuration_index in range(6):
        for variant_index, variant in enumerate(
            ("no_memory", "short_memory_k2", "object_memory")
        ):
            rows.append(
                {
                    "configuration_id": f"holdout_{configuration_index}",
                    "memory": variant,
                    "success": True,
                    "success_at_18": True,
                    "success_at_72": True,
                    "success_at_2048": True,
                    "steps": 10 - (variant_index == 2),
                    "target_reacquisition_action_count": 7 - (
                        variant_index == 2
                    ),
                    "translation_action_count": 1,
                    "translation_distance_meters": 0.25,
                    "search_rotation_count": 4,
                    "repeated_viewpoint_visit_count": 3,
                    "shared_search_entry_recovery_action_count": 0,
                    "shared_search_coverage_action_count": 4,
                    "shared_route_action_recovery_action_count": 0,
                    "integrity_errors": [],
                }
            )
    source = {
        "matrix_complete": True,
        "integrity_valid": True,
        "rows": rows,
        "code_revision": "a" * 40,
        "matrix_manifest_digest": "b" * 64,
    }
    source["result_digest"] = stable_digest(source)
    result = module.aggregate(source)
    assert result["success_counts"]["object_memory"]["eventual"] == 6
    assert result["metrics"]["steps"]["object_minus_no"]["differences"] == [
        -1,
        -1,
        -1,
        -1,
        -1,
        -1,
    ]

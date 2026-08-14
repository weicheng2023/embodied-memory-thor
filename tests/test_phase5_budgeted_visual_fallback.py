from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
from pathlib import Path

import pytest

from embodied_memory_thor.phase5.anchors import (
    VISUAL_FALLBACK_ACTION_LIMIT,
    VISUAL_FALLBACK_POLICY_VERSION,
)
from embodied_memory_thor.phase5.budgeted_fallback import (
    BUDGETED_VISUAL_FALLBACK_ACTION_LIMIT,
    BUDGETED_VISUAL_FALLBACK_POLICY_VERSION,
    BudgetedVisualFallbackConstructionError,
    build_target_independent_budgeted_visual_fallback_route,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "phase5_r2_budgeted_visual_fallback_v1.json"
EVIDENCE_PATH = (
    ROOT / "docs" / "evidence"
    / "phase5_floorplan6_r2_budgeted_fallback_construction_v1.json"
)


def _grid(width: int, height: int) -> list[dict[str, float]]:
    return [
        {"x": x * 0.25, "y": 0.9, "z": z * 0.25}
        for x in range(width)
        for z in range(height)
    ]


def _route(positions: list[dict[str, float]], **overrides: object) -> dict[str, object]:
    arguments: dict[str, object] = {
        "reachable_positions": positions,
        "start_position": {"x": 0.0, "y": 0.9, "z": 0.0},
        "start_yaw": 17.0,
        "start_camera_horizon_degrees": 60.000015,
        "grid_size": 0.25,
        "bin_size_steps": 3,
        "action_limit": 2048,
    }
    arguments.update(overrides)
    return build_target_independent_budgeted_visual_fallback_route(**arguments)  # type: ignore[arg-type]


def _diagnostic_module() -> object:
    path = ROOT / "scripts" / "diagnose_phase5_r2_budgeted_fallback_construction.py"
    spec = importlib.util.spec_from_file_location("budgeted_construction", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_budgeted_viewpoint_selection_is_input_order_independent() -> None:
    positions = _grid(7, 7)
    forward = _route(positions)
    reversed_route = _route(list(reversed(positions)))
    interleaved = _route(positions[::2] + positions[1::2])
    assert forward == reversed_route == interleaved
    assert forward["route_digest"] == reversed_route["route_digest"]


def test_builder_signature_cannot_receive_target_memory_or_outcome() -> None:
    names = set(inspect.signature(
        build_target_independent_budgeted_visual_fallback_route
    ).parameters)
    forbidden_fragments = (
        "cup", "coffee", "target", "object", "anchor", "candidate",
        "outcome", "memory", "variant", "success", "failure",
    )
    assert not any(fragment in name.lower() for name in names for fragment in forbidden_fragments)
    assert names == {
        "reachable_positions", "start_position", "start_yaw",
        "start_camera_horizon_degrees", "grid_size", "bin_size_steps",
        "action_limit",
    }


def test_route_is_coordinate_and_identity_free_and_under_budget() -> None:
    route = _route(_grid(12, 10))
    encoded = json.dumps(route, sort_keys=True)
    assert '"x"' not in encoded and '"y"' not in encoded and '"z"' not in encoded
    assert "Cup" not in encoded and "CoffeeMachine" not in encoded
    assert "objectId" not in encoded and "reachable_positions" not in encoded
    assert route["action_count"] == len(route["actions"])
    assert route["action_count"] <= BUDGETED_VISUAL_FALLBACK_ACTION_LIMIT
    assert route["target_or_anchor_input_used"] is False
    assert route["qualification_goal_input_used"] is False
    assert route["memory_input_used"] is False
    assert route["memory_variant_input_used"] is False
    assert route["candidate_outcome_input_used"] is False


def test_every_viewpoint_receives_fixed_two_horizon_cardinal_scan() -> None:
    route = _route(_grid(6, 6), start_camera_horizon_degrees=0.0)
    actions = route["actions"]
    viewpoint_count = route["viewpoint_count"]
    zero = [row for row in actions if row["phase"] == "budgeted_visual_fallback_scan_zero"]
    down = [row for row in actions if row["phase"] == "budgeted_visual_fallback_scan_downward"]
    look_down = [row for row in actions if row["phase"] == "budgeted_visual_fallback_horizon_down"]
    look_up = [row for row in actions if row["phase"] == "budgeted_visual_fallback_horizon_zero"]
    assert len(zero) == 4 * viewpoint_count
    assert len(down) == 4 * viewpoint_count
    assert len(look_down) == viewpoint_count
    assert len(look_up) == viewpoint_count
    assert route["scan_horizons_degrees"] == [0.0, 30.0]


def test_fixed_binning_reports_nominal_geometric_coverage_without_los_claim() -> None:
    route = _route(_grid(6, 6))
    coverage = route["coverage_summary"]
    assert route["viewpoint_count"] == 4
    assert coverage == {
        "occupied_bin_count": 4,
        "occupied_bins_with_viewpoint_count": 4,
        "all_occupied_bins_represented": True,
        "maximum_within_bin_grid_chebyshev_distance": 2,
        "line_of_sight_coverage_claimed": False,
    }


def test_exact_action_limit_fails_closed() -> None:
    with pytest.raises(
        BudgetedVisualFallbackConstructionError,
        match="budgeted visual fallback action limit exceeded",
    ) as caught:
        _route(_grid(1, 1), start_camera_horizon_degrees=0.0, action_limit=9)
    assert caught.value.route["action_count"] == 10
    assert caught.value.route["viewpoint_count"] == 1
    assert isinstance(caught.value.route["route_digest"], str)


def test_policy_is_shared_and_historical_artifacts_are_hash_frozen() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["policy_version"] == BUDGETED_VISUAL_FALLBACK_POLICY_VERSION
    assert config["action_limit"] == 2048
    assert config["shared_variant_contract"] == [
        "no_memory", "short_memory_k2", "object_memory"
    ]
    assert config["route_execution_allowed"] is False
    assert config["qualification_allowed"] is False
    for relative, expected in config["historical_artifacts_frozen"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected


def test_old_exhaustive_policy_contract_remains_unchanged() -> None:
    assert VISUAL_FALLBACK_POLICY_VERSION == "phase5-target-independent-exhaustive-visual-v1"
    assert VISUAL_FALLBACK_ACTION_LIMIT == 2048


def test_public_diagnostic_summary_contains_no_graph_coordinate_or_identity() -> None:
    module = _diagnostic_module()
    route = _route(_grid(6, 6))
    summary = module._summary(  # type: ignore[attr-defined]
        scene="FloorPlan6",
        classification="budgeted_visual_fallback_construction_passed",
        route=route,
        failure_reason="",
        restoration_passed=True,
        git_state={
            "code_revision": "a" * 40,
            "upstream_revision": "a" * 40,
            "working_tree_dirty": False,
            "head_pushed": True,
        },
    )
    encoded = json.dumps(summary, sort_keys=True)
    assert '"x"' not in encoded and '"y"' not in encoded and '"z"' not in encoded
    assert "objectId" not in encoded and "reachable_positions" not in encoded
    assert "Cup|" not in encoded and "CoffeeMachine|" not in encoded
    assert "actions" not in summary
    assert "reachable_node_count" not in summary
    assert summary["route_actions_executed"] is False
    assert summary["qualification_run"] is False


def test_restoration_uses_established_metadata_and_empty_inventory_contract() -> None:
    module = _diagnostic_module()
    assert module._restoration_is_clean({  # type: ignore[attr-defined]
        "agent": {"position": {}}, "inventoryObjects": []
    })
    assert not module._restoration_is_clean({  # type: ignore[attr-defined]
        "agent": {"position": {}}, "inventoryObjects": [{"objectId": "private"}]
    })
    assert not module._restoration_is_clean({})  # type: ignore[attr-defined]


def test_floorplan6_public_construction_evidence_is_safe_and_bounded() -> None:
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    encoded = json.dumps(evidence, sort_keys=True)
    assert evidence["classification"] == "budgeted_visual_fallback_construction_passed"
    assert evidence["action_count"] == 404 <= evidence["action_limit"] == 2048
    assert evidence["viewpoint_count"] == 26
    assert evidence["route_digest"] == (
        "aa40a6e0f5aed9c899de48cbaa4f79520f6a7b0f687fb8154ab833afd338b5af"
    )
    assert evidence["reset_restoration_passed"] is True
    assert evidence["route_actions_executed"] is False
    assert evidence["qualification_run"] is False
    assert '"x"' not in encoded and '"y"' not in encoded and '"z"' not in encoded
    assert "objectId" not in encoded and "reachable_positions" not in encoded
    assert "Cup|" not in encoded and "CoffeeMachine|" not in encoded

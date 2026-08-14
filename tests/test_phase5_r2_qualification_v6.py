from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from embodied_memory_thor.phase5.budgeted_fallback import (
    BUDGETED_VISUAL_FALLBACK_POLICY_VERSION,
    build_target_independent_budgeted_visual_fallback_route,
)
from embodied_memory_thor.phase5.r2_stability import (
    STABILITY_OVERBOUND_SELECTION_POLICY,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "phase5_r2_qualification_v6.json"
FLOORPLAN6_CONFIG = ROOT / "configs" / "phase5_r2_floorplan6_qualified_configuration_v1.json"
FLOORPLAN6_EVIDENCE = ROOT / "docs" / "evidence" / "phase5_floorplan6_r2_qualification_v6.json"


def _module() -> object:
    path = ROOT / "scripts" / "qualify_phase5_r2_v6.py"
    spec = importlib.util.spec_from_file_location("phase5_r2_v6_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _route() -> dict[str, object]:
    positions = [
        {"x": x * 0.25, "y": 0.9, "z": z * 0.25}
        for x in range(6) for z in range(6)
    ]
    return build_target_independent_budgeted_visual_fallback_route(
        reachable_positions=positions,
        start_position=positions[0],
        start_yaw=0.0,
        start_camera_horizon_degrees=0.0,
    )


def test_v6_config_freezes_predecessor_and_registered_evidence() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["qualification_version"] == "phase5-r2-native-qualification-v6"
    assert config["fallback_policy_version"] == BUDGETED_VISUAL_FALLBACK_POLICY_VERSION
    assert config["fallback_action_limit"] == 2048
    assert config["authorized_scene_order"] == [
        "FloorPlan6", "FloorPlan7", "FloorPlan8",
        "FloorPlan10", "FloorPlan13", "FloorPlan16",
    ]
    assert config["qualification_runs_memory_variants"] is False
    assert config["formal_use_allowed"] is False
    for relative, expected in config["historical_artifacts_frozen"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_v6_validation_rejects_later_or_unregistered_scene() -> None:
    module = _module()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    module._validate_config(config, "FloorPlan6")  # type: ignore[attr-defined]
    for scene in ("FloorPlan5", "FloorPlan17", "FloorPlan30"):
        try:
            module._validate_config(config, scene)  # type: ignore[attr-defined]
        except ValueError as exc:
            assert "outside" in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"unregistered scene accepted: {scene}")


def test_v6_patches_only_the_fallback_policy_and_version_contract() -> None:
    module = _module()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    v5 = module._v5_module()  # type: ignore[attr-defined]
    original_pairs = v5._candidate_pairs
    original_selector = v5.select_stability_pose_budget
    patched = module._patch_v5(v5, config)  # type: ignore[attr-defined]
    assert patched.QUALIFICATION_VERSION == "phase5-r2-native-qualification-v6"
    assert patched.VISUAL_FALLBACK_POLICY_VERSION == BUDGETED_VISUAL_FALLBACK_POLICY_VERSION
    assert patched.build_target_independent_visual_fallback_route is (
        build_target_independent_budgeted_visual_fallback_route
    )
    assert patched._candidate_pairs is original_pairs
    assert patched.select_stability_pose_budget is original_selector


def test_v6_maps_budgeted_construction_and_reacquisition_classes() -> None:
    module = _module()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    patched = module._patch_v5(module._v5_module(), config)  # type: ignore[attr-defined]
    assert patched.classify_candidate_batch([{
        "prebuild_error": "BudgetedVisualFallbackConstructionError: budgeted visual fallback action limit exceeded"
    }]) == "budgeted_visual_fallback_construction_ineligible"
    assert patched.classify_candidate_batch([{
        "first_trial": {"reason": "target_not_rediscovered_before_fallback_exhaustion"},
        "reason": "target_not_rediscovered_before_fallback_exhaustion",
        "prebuild_error": "",
    }]) == "budgeted_visual_fallback_reacquisition_not_achieved"


def test_v6_public_summary_adds_only_coordinate_free_budget_metrics() -> None:
    module = _module()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    patched = module._patch_v5(module._v5_module(), config)  # type: ignore[attr-defined]
    route = _route()
    summary = patched.build_public_summary(
        scene="FloorPlan6",
        git_state={
            "code_revision": "a" * 40,
            "upstream_revision": "a" * 40,
            "working_tree_dirty": False,
            "head_pushed": True,
        },
        output_dir=Path("outputs/private"),
        cup_audit=[{"cup_order": 1, "selected": True}],
        stability_audit=[{"stable": True, "classification": "stable"}],
        candidate_plan={
            "candidate_plan_digest": "b" * 64,
            "candidate_pairs": [{"fallback_route": route}],
        },
        trials=[],
        selected_public=None,
        selected_private=None,
        classification="budgeted_visual_fallback_reacquisition_not_achieved",
        failure_reason="fixture",
        restoration={"passed": True},
        pose_selection={
            "observed_pose_count": 1,
            "selected_pose_count": 1,
            "omitted_pose_count": 0,
            "pose_budget": 256,
            "selection_policy": STABILITY_OVERBOUND_SELECTION_POLICY,
            "selection_applied": False,
            "selection_before_trial_outcomes": True,
            "selection_digest": "c" * 64,
        },
    )
    encoded = json.dumps(summary, sort_keys=True)
    assert summary["qualification_version"] == "phase5-r2-native-qualification-v6"
    assert summary["fallback_policy_version"] == BUDGETED_VISUAL_FALLBACK_POLICY_VERSION
    assert summary["fallback_action_count_min"] == route["action_count"]
    assert summary["fallback_viewpoint_count_min"] == route["viewpoint_count"]
    assert summary["fallback_candidate_outcome_input_used"] is False
    assert summary["fallback_memory_input_used"] is False
    assert summary["scene_skip_allowed"] is True
    for forbidden in ('"x"', '"y"', '"z"', "Cup|", "CoffeeMachine|", "objectId"):
        assert forbidden not in encoded


def test_v6_public_route_uses_distinct_budgeted_route_id() -> None:
    module = _module()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    patched = module._patch_v5(module._v5_module(), config)  # type: ignore[attr-defined]
    public = patched._public_route(
        patched._legacy(),
        route_id="FloorPlan6_R2_fixed_start_001_fallback_visual_v1",
        scene="FloorPlan6",
        source_digest="d" * 64,
        route=_route(),
        role="target_independent_fallback",
    )
    assert public["route_id"].endswith("fallback_budgeted_visual_v1")
    assert public["target_or_anchor_input_used"] is False


def test_floorplan6_v6_qualified_evidence_and_configuration_are_safe() -> None:
    evidence = json.loads(FLOORPLAN6_EVIDENCE.read_text(encoding="utf-8"))
    configuration = json.loads(FLOORPLAN6_CONFIG.read_text(encoding="utf-8"))
    assert evidence["passed"] is True
    assert evidence["qualified_r2_count_after_scene"] == 4
    assert evidence["candidate_trials_executed"] == 1
    assert evidence["fresh_reset_replay_passed"] is True
    assert evidence["reset_restoration_passed"] is True
    assert evidence["fallback_route_action_count"] == 403 <= 2048
    assert evidence["fallback_viewpoint_count"] == 26
    assert configuration["configuration_id"] == evidence["configuration_id"]
    assert configuration["source_qualification_digest"] == evidence[
        "source_qualification_digest"
    ]
    assert configuration["fallback_route"]["action_count"] == 403
    assert len(configuration["fallback_route"]["action_codes"]) == 403
    serialized = json.dumps({"evidence": evidence, "configuration": configuration})
    for forbidden in ('"x"', '"y"', '"z"', "Cup|", "CoffeeMachine|", "objectId"):
        assert forbidden not in serialized

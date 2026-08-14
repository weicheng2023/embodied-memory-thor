from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from embodied_memory_thor.phase5.budgeted_fallback import (
    BUDGETED_VISUAL_FALLBACK_POLICY_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_r2_replacement_qualification_v7.json"
SCRIPT = ROOT / "scripts" / "qualify_phase5_r2_replacement_v7.py"


def _module() -> object:
    spec = importlib.util.spec_from_file_location("phase5_r2_replacement_v7", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_replacement_protocol_excludes_floorplan10_and_preserves_five() -> None:
    config = _config()
    assert config["excluded_configuration_id"] == "FloorPlan10_R2_fixed_start_001"
    assert config["retained_qualified_configuration_order"] == [
        "FloorPlan3_R2_fixed_start_001",
        "FloorPlan4_R2_fixed_start_001",
        "FloorPlan6_R2_fixed_start_001",
        "FloorPlan7_R2_fixed_start_001",
        "FloorPlan12_R2_fixed_start_001",
    ]
    assert config["authorized_scene_order"] == [
        f"FloorPlan{index}" for index in range(17, 31)
    ]
    assert config["stop_after_first_qualified_replacement"] is True


def test_replacement_protocol_preserves_budget_privacy_and_no_memory_runs() -> None:
    config = _config()
    assert config["fallback_policy_version"] == (
        BUDGETED_VISUAL_FALLBACK_POLICY_VERSION
    )
    assert config["fallback_action_limit"] == 2048
    assert config["candidate_pair_limit"] == 12
    assert config["qualification_runs_memory_variants"] is False
    assert config["formal_use_allowed"] is False
    assert config["images_saved"] is False
    assert config["gui_enabled"] is False
    assert config["fallback_target_or_anchor_input_used"] is False
    assert config["fallback_candidate_outcome_input_used"] is False
    assert config["fallback_memory_input_used"] is False


def test_replacement_requires_clean_production_equivalent_no_memory_gate() -> None:
    gate = _config()["production_equivalent_gate_requirements"]
    assert gate == {
        "memory": "no_memory",
        "included_in_formal_aggregate": False,
        "max_steps": 2048,
        "task_success": True,
        "information_boundary_passed": True,
        "shared_search_action_failure_count": 0,
        "shared_subgoal_action_failure_count": 0,
        "shared_route_action_recovery_attempt_count": 0,
        "shared_route_action_recovery_action_count": 0,
        "shared_route_action_recovery_terminal_failure_count": 0,
    }


def test_replacement_config_hash_freezes_predecessors_and_stop_evidence() -> None:
    config = _config()
    changed = [
        relative
        for relative, expected in config["historical_artifacts_frozen"].items()
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected
    ]
    assert changed == []
    assert "docs/evidence/phase5_r2_floorplan10_route_action_recovery_gate_v1_stop.json" in (
        config["historical_artifacts_frozen"]
    )


def test_replacement_validation_accepts_only_preregistered_later_scenes() -> None:
    module = _module()
    config = _config()
    module._validate_config(config, "FloorPlan17")  # type: ignore[attr-defined]
    module._validate_config(config, "FloorPlan30")  # type: ignore[attr-defined]
    for scene in ("FloorPlan10", "FloorPlan16", "FloorPlan31"):
        with pytest.raises(ValueError, match="outside"):
            module._validate_config(config, scene)  # type: ignore[attr-defined]


def test_replacement_patch_changes_version_not_candidate_or_fallback_policy() -> None:
    module = _module()
    config = _config()
    patched = module._patched_qualifier(config)  # type: ignore[attr-defined]
    assert patched.QUALIFICATION_VERSION == (
        "phase5-r2-replacement-native-qualification-v7"
    )
    assert patched.VISUAL_FALLBACK_POLICY_VERSION == (
        BUDGETED_VISUAL_FALLBACK_POLICY_VERSION
    )
    summary = patched.build_public_summary(
        scene="FloorPlan17",
        git_state={
            "code_revision": "a" * 40,
            "upstream_revision": "a" * 40,
            "working_tree_dirty": False,
            "head_pushed": True,
        },
        output_dir=Path("outputs/private"),
        cup_audit=[],
        stability_audit=[],
        candidate_plan={"candidate_pairs": []},
        trials=[],
        selected_public=None,
        selected_private=None,
        classification="scene_start_ineligible_no_standing_cup",
        failure_reason="fixture",
        restoration={"passed": True},
        pose_selection={
            "observed_pose_count": 0,
            "selected_pose_count": 0,
            "omitted_pose_count": 0,
            "pose_budget": 256,
            "selection_policy": "fixed_digest_even_stride_v1",
            "selection_applied": False,
            "selection_before_trial_outcomes": True,
            "selection_digest": "b" * 64,
        },
    )
    assert summary["replacement_freeze_allowed"] is False
    assert summary["production_equivalent_gate_required"] is True
    assert summary["production_equivalent_gate_passed"] is False
    encoded = json.dumps(summary, sort_keys=True)
    for forbidden in ('"x"', '"y"', '"z"', "Cup|", "CoffeeMachine|", "objectId"):
        assert forbidden not in encoded

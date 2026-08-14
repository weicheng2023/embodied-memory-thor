from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_r2_floorplan17_production_gate_v1.json"
CANDIDATE = ROOT / "configs" / "phase5_r2_floorplan17_replacement_candidate_v1.json"
EVIDENCE = ROOT / "docs" / "evidence" / "phase5_floorplan17_r2_replacement_qualification_v7.json"
SCRIPT = ROOT / "scripts" / "run_phase5_r2_floorplan17_production_gate_v1.py"


def _module() -> object:
    spec = importlib.util.spec_from_file_location("phase5_floorplan17_gate", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_floorplan17_native_candidate_passes_but_is_not_yet_frozen() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    assert evidence["passed"] is True
    assert evidence["fresh_reset_replay_passed"] is True
    assert evidence["reset_restoration_passed"] is True
    assert evidence["candidate_trials_executed"] == 1
    assert evidence["fallback_route_action_count"] == 212 <= 2048
    assert evidence["subgoal_route_action_count"] == 4
    assert evidence["production_equivalent_gate_passed"] is False
    assert evidence["replacement_freeze_allowed"] is False
    assert candidate["configuration_id"] == evidence["configuration_id"]
    assert candidate["production_equivalent_gate_passed"] is False
    assert candidate["replacement_freeze_allowed"] is False


def test_floorplan17_public_candidate_is_action_only_and_private_free() -> None:
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    assert candidate["subgoal_route"]["action_sequence_digest"] == (
        "24c0b4be69b2895d473c7f6774164d3023e89a8b243c3d72ac04502586e6a1e2"
    )
    assert candidate["fallback_route"]["action_sequence_digest"] == (
        "ac1570573adc8277c9f39df10970893189133b9cbd413da313debd1477210fa8"
    )
    assert len(candidate["subgoal_route"]["action_codes"]) == 4
    assert len(candidate["fallback_route"]["action_codes"]) == 212
    serialized = json.dumps(candidate, sort_keys=True)
    for forbidden in (
        '"x"', '"y"', '"z"', '"objectId"', "Cup|", "CoffeeMachine|",
        "TeleportFull", "target_point", "reachable_positions",
    ):
        assert forbidden not in serialized


def test_production_gate_is_one_excluded_no_memory_episode() -> None:
    config = _config()
    assert config["configuration_id"] == "FloorPlan17_R2_fixed_start_001"
    assert config["memory"] == "no_memory"
    assert "variants" not in config
    assert config["max_steps"] == 2048
    assert config["included_in_formal_aggregate"] is False
    assert config["formal_execution_authorized"] is False
    assert config["save_frames"] is False
    assert config["visualize"] is False
    required = config["required_outcomes"]
    assert required["shared_search_action_failure_count"] == 0
    assert required["shared_subgoal_action_failure_count"] == 0
    assert required["shared_route_action_recovery_attempt_count"] == 0
    assert required["shared_route_action_recovery_action_count"] == 0


def test_production_gate_hash_freezes_public_and_private_candidate() -> None:
    config = _config()
    changed = [
        relative
        for relative, expected in config["historical_artifacts_frozen"].items()
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected
    ]
    assert changed == []
    private_path = (
        ROOT
        / "outputs"
        / "phase5_r2_replacement_v7_floorplan17_38af4c6"
        / "evaluator_only_configuration_registry_draft.json"
    )
    assert hashlib.sha256(private_path.read_bytes()).hexdigest() == (
        config["private_candidate_sha256"]
    )


def test_runtime_join_validates_private_pose_without_public_leak() -> None:
    runtime = _module().load_candidate_runtime()
    assert runtime.configuration.configuration_id == (
        "FloorPlan17_R2_fixed_start_001"
    )
    assert runtime.subgoal_route.action_count == 4
    assert runtime.fallback_route.action_count == 212
    public = json.dumps(runtime.configuration.public_reference(), sort_keys=True)
    for forbidden in (
        '"x"', '"y"', '"z"', '"objectId"', "Cup|", "CoffeeMachine|",
        "TeleportFull",
    ):
        assert forbidden not in public


def test_production_gate_audit_requires_success_and_zero_route_recovery() -> None:
    module = _module()
    runtime = module.load_candidate_runtime()
    summary = {
        "success": True,
        "failure_reason": "",
        "setup_completed": True,
        "setup_failure_reason": "",
        "information_boundary_passed": True,
        "included_in_formal_aggregate": False,
        "shared_search_route_id": runtime.fallback_route.route_id,
        "shared_search_action_sequence_digest": runtime.fallback_route.action_sequence_digest,
        "shared_subgoal_route_id": runtime.subgoal_route.route_id,
        "shared_subgoal_action_sequence_digest": runtime.subgoal_route.action_sequence_digest,
        "shared_search_action_failure_count": 0,
        "shared_subgoal_action_failure_count": 0,
        "shared_search_route_entry_mismatch_count": 0,
        "shared_subgoal_route_entry_mismatch_count": 0,
        "shared_route_action_recovery_attempt_count": 0,
        "shared_route_action_recovery_action_count": 0,
        "shared_route_action_recovered_failure_count": 0,
        "shared_route_action_recovery_terminal_failure_count": 0,
        "shared_route_action_recovery_pending_action_count": 0,
        "invalid_planner_decision_count": 0,
        "target_lock_terminal_failure_count": 0,
        "steps": 220,
        "task_progress": {"ordered_subgoal_passed": True},
        "shared_subgoal_coverage_action_count": 4,
        "shared_search_coverage_action_count": 200,
        "invalid_action_count": 0,
        "target_lock_interaction_recovery_action_count": 0,
    }
    with tempfile.TemporaryDirectory() as temporary_dir:
        episode_dir = Path(temporary_dir)
        (episode_dir / "episode.jsonl").write_text(
            json.dumps({"planner_input": {"request": {"shared_search": None}}})
            + "\n",
            encoding="utf-8",
        )
        errors, metrics = module._audit_episode(
            summary=summary,
            episode_dir=episode_dir,
            runtime=runtime,
        )
    assert errors == []
    assert metrics["route_action_recovery_phases"] == []

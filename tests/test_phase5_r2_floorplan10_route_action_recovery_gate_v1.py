from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_r2_floorplan10_route_action_recovery_gate_v1.json"
SCRIPT = ROOT / "scripts" / "run_phase5_r2_floorplan10_route_action_recovery_gate_v1.py"
EVIDENCE = (
    ROOT
    / "docs"
    / "evidence"
    / "phase5_r2_floorplan10_route_action_recovery_gate_v1_stop.json"
)


def _module() -> object:
    spec = importlib.util.spec_from_file_location("phase5_route_recovery_gate", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_gate_is_one_excluded_floorplan10_no_memory_replay() -> None:
    config = _config()
    assert config["configuration_id"] == "FloorPlan10_R2_fixed_start_001"
    assert config["memory"] == "no_memory"
    assert "variants" not in config
    assert config["max_steps"] == 2048
    assert config["included_in_formal_aggregate"] is False
    assert config["formal_execution_authorized"] is False
    assert config["save_frames"] is False
    assert config["visualize"] is False


def test_gate_hash_freezes_implementation_stop_evidence_and_runtime() -> None:
    config = _config()
    changed = [
        relative
        for relative, expected in config["historical_artifacts_frozen"].items()
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected
    ]
    assert changed == []
    assert "docs/evidence/phase5_real_formal_pilot_v4_invalidated_stop.json" in (
        config["historical_artifacts_frozen"]
    )
    assert "configs/phase5_r2_search_routes_v2.json" in (
        config["historical_artifacts_frozen"]
    )


def test_gate_contract_requires_exact_failed_action_stabilization_and_retry() -> None:
    config = _config()
    assert config["route_action_recovery_policy"] == (
        "phase5-shared-route-action-recovery-v1"
    )
    assert config["route_action_recovery_attempt_limit"] == 4
    assert config["route_action_recovery_action_limit"] == 8
    assert config["expected_failed_action_index"] == 200
    assert config["expected_phases"] == [
        "coverage",
        "route_action_stabilization",
        "route_action_retry",
    ]
    assert config["expected_actions"] == ["MoveAhead", "Pass", "MoveAhead"]


def test_gate_audit_requires_exercised_recovery_and_public_directives() -> None:
    module = _module()
    summary = {
        "success": True,
        "failure_reason": "",
        "setup_completed": True,
        "setup_failure_reason": "",
        "information_boundary_passed": True,
        "included_in_formal_aggregate": False,
        "shared_route_action_recovery_policy": (
            "phase5-shared-route-action-recovery-v1"
        ),
        "shared_route_action_recovery_attempt_limit": 4,
        "shared_route_action_recovery_action_limit": 8,
        "shared_route_action_recovery_attempt_count": 1,
        "shared_route_action_recovery_action_count": 2,
        "shared_route_action_recovered_failure_count": 1,
        "shared_route_action_recovery_terminal_failure_count": 0,
        "shared_route_action_recovery_pending_action_count": 0,
        "shared_search_action_failure_count": 0,
        "invalid_planner_decision_count": 0,
        "invalid_action_count": 1,
        "steps": 218,
        "task_progress": {"ordered_subgoal_passed": True},
    }
    rows = []
    for phase, action, success in (
        ("coverage", "MoveAhead", False),
        ("route_action_stabilization", "Pass", True),
        ("route_action_retry", "MoveAhead", True),
    ):
        directive = {
            "action": {"action": action},
            "action_index": 200,
            "action_sequence_digest": "a" * 64,
            "phase": phase,
            "policy": "frozen_target_independent_route",
            "route_id": "opaque-route",
            "route_role": "target_independent_fallback",
        }
        rows.append(
            {
                "planner_input": {"request": {"shared_search": directive}},
                "planner_decision": {"action": {"action": action}},
                "environment_feedback": {"action_success": success},
            }
        )
    with tempfile.TemporaryDirectory() as temporary_dir:
        episode_dir = Path(temporary_dir)
        (episode_dir / "episode.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        errors, public = module._audit_episode(
            summary=summary,
            episode_dir=episode_dir,
        )
    assert errors == []
    assert public["route_action_recovery_actions"] == [
        "MoveAhead",
        "Pass",
        "MoveAhead",
    ]
    assert public["recovery_directives_public_schema_only"] is True


def test_gate_public_config_contains_no_private_runtime_material() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    for forbidden in (
        '"start_pose"',
        '"target_point"',
        '"anchor_id"',
        '"objectId"',
        '"reachable_positions"',
        "TeleportFull",
        "PlaceObjectAtPoint",
    ):
        assert forbidden not in text


def test_real_gate_stop_evidence_records_persistent_failure_and_stays_excluded() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["passed"] is False
    assert evidence["success"] is False
    assert evidence["classification"] == (
        "persistent_route_obstacle_not_transient_settling"
    )
    assert evidence["steps"] == 217
    assert evidence["failed_action_index"] == 200
    assert evidence["recovery_actions"] == ["MoveAhead", "Pass", "MoveAhead"]
    assert evidence["recovery_action_successes"] == [False, True, False]
    assert evidence["recovery_attempt_count"] == 1
    assert evidence["recovery_action_count"] == 2
    assert evidence["recovered_failure_count"] == 0
    assert evidence["terminal_failure_count"] == 1
    assert evidence["information_boundary_passed"] is True
    assert evidence["included_in_formal_aggregate"] is False
    text = EVIDENCE.read_text(encoding="utf-8")
    for forbidden in (
        '"objectId"',
        '"target_point"',
        '"anchor_id"',
        '"support_id"',
        '"reachable_positions"',
        "TeleportFull",
        "PlaceObjectAtPoint",
    ):
        assert forbidden not in text

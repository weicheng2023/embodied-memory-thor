from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_r1_target_lock_recovery_gate_v2.json"
SCRIPT = ROOT / "scripts" / "run_phase5_r1_target_lock_recovery_gate_v2.py"
EVIDENCE = ROOT / "docs" / "evidence" / "phase5_r1_target_lock_recovery_gate_v2.json"


def _module() -> object:
    spec = importlib.util.spec_from_file_location("phase5_target_lock_gate_v2", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_gate_is_one_excluded_failed_cell_replay_not_a_variant_matrix() -> None:
    config = _config()
    assert config["configuration_id"] == "FloorPlan306_R1_fixed_start_001"
    assert config["memory"] == "object_memory"
    assert "variants" not in config
    assert config["max_steps"] == 64
    assert config["included_in_formal_aggregate"] is False
    assert config["formal_execution_authorized"] is False
    assert config["save_frames"] is False
    assert config["visualize"] is False


def test_gate_hash_freeze_detects_only_post_pass_formal_v4_successor_sources() -> None:
    config = _config()
    changed = [
        relative
        for relative, expected in config["historical_artifacts_frozen"].items()
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected
    ]
    assert changed == [
        "src/embodied_memory_thor/phase5/target_lock.py",
        "src/embodied_memory_thor/phase4/runner.py",
    ]
    assert "docs/evidence/phase5_real_formal_pilot_v3_invalidated_stop.json" in (
        config["historical_artifacts_frozen"]
    )
    assert "src/embodied_memory_thor/phase5/target_lock.py" in (
        config["historical_artifacts_frozen"]
    )


def test_gate_contract_binds_fixed_bounded_recovery() -> None:
    config = _config()
    assert config["target_lock_policy"] == "phase5-shared-target-lock-v2"
    assert config["canonical_pickup_horizon_degrees"] == -30
    assert config["interaction_recovery_action_limit"] == 4
    assert config["interaction_recovery_retry_limit"] == 1
    assert config["expected_target_lock_actions"] == [
        "PickupObject",
        "LookUp",
        "PickupObject",
    ]


def test_gate_audit_requires_exercised_collision_recovery_and_safe_directive() -> None:
    module = _module()
    summary = {
        "success": True,
        "failure_reason": "",
        "setup_completed": True,
        "setup_failure_reason": "",
        "information_boundary_passed": True,
        "included_in_formal_aggregate": False,
        "book_distraction_policy": "phase5-book-distraction-v4",
        "policy": "phase5-shared-target-lock-v2",
        "target_lock_pickup_attempt_count": 2,
        "target_lock_interaction_recovery_action_count": 1,
        "target_lock_interaction_recovery_attempt_count": 1,
        "target_lock_terminal_failure_count": 0,
        "target_lock_failed_reason": "",
        "failed_interaction_count": 1,
        "invalid_action_count": 1,
        "steps": 9,
    }
    rows = []
    for action, success, horizon, phase in (
        ("PickupObject", False, 0.0, "pickup_attempt"),
        ("LookUp", True, 0.0, "interaction_recovery"),
        ("PickupObject", True, -30.0, "pickup_attempt"),
    ):
        action_payload = {"action": action}
        if action == "PickupObject":
            action_payload["objectId"] = "visible-current-observation"
        rows.append(
            {
                "planner_decision": {
                    "reason_code": f"target_lock_{phase}",
                    "action": action_payload,
                },
                "planner_input": {
                    "request": {
                        "observation": {"agent": {"cameraHorizon": horizon}}
                    }
                },
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
    assert public["interaction_recovery_action_contains_only_action_name"] is True
    assert "visible-current-observation" not in json.dumps(public)


def test_gate_public_result_forbids_identity_coordinates_and_native_setup_actions() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "FORBIDDEN_PUBLIC_TOKENS" in source
    config_text = CONFIG.read_text(encoding="utf-8")
    for forbidden in (
        '"start_pose"',
        '"target_point"',
        '"anchor_id"',
        '"objectId"',
        "Book|",
        "TeleportFull",
        "PlaceObjectAtPoint",
    ):
        assert forbidden not in config_text


def test_real_gate_evidence_records_exercised_recovery_and_stays_excluded() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["passed"] is True
    assert evidence["success"] is True
    assert evidence["steps"] == 9
    assert evidence["failed_interaction_count"] == 1
    assert evidence["invalid_action_count"] == 1
    assert evidence["interaction_recovery_action_count"] == 1
    assert evidence["interaction_recovery_attempt_count"] == 1
    assert evidence["terminal_failure_count"] == 0
    assert evidence["target_lock_actions"] == [
        "PickupObject",
        "LookUp",
        "PickupObject",
    ]
    assert evidence["target_lock_action_successes"] == [False, True, True]
    assert evidence["target_lock_camera_horizons_degrees"] == [0, 0, -30]
    assert evidence["information_boundary_passed"] is True
    assert evidence["included_in_formal_aggregate"] is False
    text = EVIDENCE.read_text(encoding="utf-8")
    for forbidden in (
        '"start_pose"',
        '"target_point"',
        '"anchor_id"',
        '"objectId"',
        "Book|",
        "TeleportFull",
        "PlaceObjectAtPoint",
    ):
        assert forbidden not in text

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

from embodied_memory_thor.phase5.formal_v2 import (
    REAL_EPISODE_COUNT,
    REAL_MANIFEST_SCHEMA_VERSION_V5,
    REAL_METRIC_SCHEMA_VERSION_V6,
    REAL_PROTOCOL_VERSION_V5,
    REAL_REQUIRED_METRICS_V6,
    build_public_manifest,
    collect_public_runtime_bindings,
    validate_precommit,
    validate_public_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_real_formal_pilot_v5.json"
DRY_RUN_EVIDENCE = (
    ROOT / "docs" / "evidence"
    / "phase5_r2_runtime_v3_six_configuration_dry_run_v1.json"
)
R2_ORDER = [
    "FloorPlan3_R2_fixed_start_001",
    "FloorPlan4_R2_fixed_start_001",
    "FloorPlan6_R2_fixed_start_001",
    "FloorPlan7_R2_fixed_start_001",
    "FloorPlan12_R2_fixed_start_001",
    "FloorPlan17_R2_fixed_start_001",
]


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _manifest() -> dict:
    config = _config()
    return build_public_manifest(
        config,
        code_revision="f" * 40,
        bindings=collect_public_runtime_bindings(config, root=ROOT),
    )


def _executor() -> object:
    path = ROOT / "scripts" / "run_phase5_real_formal_pilot_v2.py"
    spec = importlib.util.spec_from_file_location("phase5_formal_v5_shared_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v5_precommit_is_readiness_only_and_binds_replacement_evidence() -> None:
    config = _config()
    validate_precommit(config, root=ROOT)
    assert config["manifest_schema_version"] == REAL_MANIFEST_SCHEMA_VERSION_V5
    assert config["protocol_version"] == REAL_PROTOCOL_VERSION_V5
    assert config["metric_schema_version"] == REAL_METRIC_SCHEMA_VERSION_V6
    assert config["formal_execution_authorized"] is False
    assert config["readiness_only_authorized"] is True
    assert config["episode_reuse_allowed"] is False
    assert config["panels"][1]["runtime_set"] == "phase5-r2-frozen-runtime-set-v3"
    assert config["panels"][1]["configuration_ids"] == R2_ORDER
    assert "FloorPlan10_R2_fixed_start_001" not in R2_ORDER
    assert str(DRY_RUN_EVIDENCE.relative_to(ROOT)).replace("\\", "/") in config[
        "historical_artifacts_frozen"
    ]
    for relative, expected in config["historical_artifacts_frozen"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_v5_public_manifest_is_fresh_54_cells_with_72_metrics() -> None:
    manifest = _manifest()
    validate_public_manifest(manifest)
    assert manifest["episode_count"] == REAL_EPISODE_COUNT == 54
    assert tuple(manifest["required_metrics"]) == REAL_REQUIRED_METRICS_V6
    assert len(REAL_REQUIRED_METRICS_V6) == 72
    r2 = [row for row in manifest["episodes"] if row["panel"] == "r2_stable"]
    assert [row["configuration_id"] for row in r2[::3]] == R2_ORDER
    assert {row["runtime_set"] for row in r2} == {
        "phase5-r2-frozen-runtime-set-v3"
    }
    assert {row["route_action_recovery_policy"] for row in manifest["episodes"]} == {
        "phase5-shared-route-action-recovery-v1"
    }
    serialized = json.dumps(manifest, sort_keys=True)
    for forbidden in (
        '"start_pose"', '"target_point"', '"anchor_id"', '"objectId"',
        "Book|", "Cup|", "CoffeeMachine|", "TeleportFull", "PlaceObjectAtPoint",
    ):
        assert forbidden not in serialized


def test_v5_readiness_joins_all_twelve_runtimes_without_thor() -> None:
    config = _config()
    readiness = _executor().build_readiness(config=config, manifest=_manifest())
    assert readiness["readiness_version"] == "phase5-real-thor-formal-readiness-v5"
    assert readiness["executor_version"] == "phase5-real-thor-formal-executor-v5"
    assert readiness["episode_count"] == 54
    assert readiness["unique_runtime_count"] == 12
    assert readiness["private_runtime_join_passed"] is True
    assert readiness["private_runtime_material_serialized"] is False
    assert readiness["formal_execution_authorized"] is False
    assert readiness["readiness_passed"] is True


def _valid_audit_fixture(temporary_dir: str) -> tuple[dict, dict, Path]:
    episode = _manifest()["episodes"][0]
    summary = {key: 0 for key in REAL_REQUIRED_METRICS_V6}
    summary.update({
        "success": True,
        "information_boundary_passed": True,
        "setup_completed": True,
        "setup_failure_reason": "",
        "included_in_formal_aggregate": True,
        "evidence_status": "formal_acceptance_candidate",
        "shared_search_action_sequence_digest": episode[
            "search_route_action_sequence_digest"
        ],
        "shared_search_route_id": episode["search_route_id"],
        "shared_subgoal_action_sequence_digest": None,
        "shared_subgoal_route_id": None,
        "shared_search_entry_recovery_policy": (
            "phase5-shared-search-entry-recovery-v1"
        ),
        "shared_search_entry_recovery_action_limit": 64,
        "book_distraction_policy": episode["book_distraction_policy"],
        "shared_search_entry_alignment_policy": (
            "phase5-shared-search-entry-alignment-v3"
        ),
        "shared_search_entry_alignment_action_limit": 4,
        "target_lock_policy": episode["target_lock_policy"],
        "target_lock_interaction_recovery_action_limit": 4,
        "target_lock_interaction_recovery_retry_limit": 1,
        "target_lock_canonical_pickup_horizon_degrees": -30.0,
        "shared_route_action_recovery_policy": episode[
            "route_action_recovery_policy"
        ],
        "shared_route_action_recovery_attempt_limit": 4,
        "shared_route_action_recovery_action_limit": 8,
        "shared_route_action_recovery_terminal_failure_count": 0,
        "shared_route_action_recovery_pending_action_count": 0,
        "invalid_planner_decision_count": 0,
        "intervention_count": 0,
        "intervention_failure_count": 0,
        "task_progress": {},
    })
    episode_dir = Path(temporary_dir)
    (episode_dir / "run_manifest.json").write_text(json.dumps({
        "included_in_formal_aggregate": True,
        "evidence_status": "formal_acceptance_candidate",
        "working_tree_dirty": False,
        "code_revision": "f" * 40,
    }), encoding="utf-8")
    (episode_dir / "setup.jsonl").write_text("{}\n", encoding="utf-8")
    (episode_dir / "episode.jsonl").write_text("{}\n", encoding="utf-8")
    (episode_dir / "evaluator_setup.jsonl").write_text("{}\n", encoding="utf-8")
    return episode, summary, episode_dir


def test_v5_successfully_recovered_route_rejection_is_performance() -> None:
    executor = _executor()
    with tempfile.TemporaryDirectory() as temporary_dir:
        episode, summary, episode_dir = _valid_audit_fixture(temporary_dir)
        summary["invalid_action_count"] = 1
        summary["failed_interaction_count"] = 1
        summary["shared_route_action_recovery_attempt_count"] = 1
        summary["shared_route_action_recovery_action_count"] = 2
        summary["shared_route_action_recovered_failure_count"] = 1
        errors = executor.audit_episode(
            episode=episode, summary=summary, episode_dir=episode_dir,
            expected_code_revision="f" * 40,
        )
    assert errors == []


def test_v5_terminal_or_pending_route_recovery_is_integrity_failure() -> None:
    executor = _executor()
    with tempfile.TemporaryDirectory() as temporary_dir:
        episode, summary, episode_dir = _valid_audit_fixture(temporary_dir)
        summary["shared_route_action_recovery_terminal_failure_count"] = 1
        summary["shared_route_action_recovery_pending_action_count"] = 1
        errors = executor.audit_episode(
            episode=episode, summary=summary, episode_dir=episode_dir,
            expected_code_revision="f" * 40,
        )
    assert "route_action_recovery_terminal_failure" in errors
    assert "route_action_recovery_pending_action" in errors

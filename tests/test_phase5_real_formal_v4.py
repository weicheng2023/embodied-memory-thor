from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

from embodied_memory_thor.phase5.formal_v2 import (
    REAL_EPISODE_COUNT,
    REAL_MANIFEST_SCHEMA_VERSION_V4,
    REAL_METRIC_SCHEMA_VERSION_V5,
    REAL_PROTOCOL_VERSION_V4,
    REAL_REQUIRED_METRICS_V5,
    build_public_manifest,
    collect_public_runtime_bindings,
    validate_precommit,
    validate_public_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_real_formal_pilot_v4.json"


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
    spec = importlib.util.spec_from_file_location("phase5_formal_v4_shared", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v4_precommit_is_readiness_only_and_hash_binds_recovery_gate() -> None:
    config = _config()
    validate_precommit(config, root=ROOT)
    assert config["manifest_schema_version"] == REAL_MANIFEST_SCHEMA_VERSION_V4
    assert config["protocol_version"] == REAL_PROTOCOL_VERSION_V4
    assert config["metric_schema_version"] == REAL_METRIC_SCHEMA_VERSION_V5
    assert config["book_distraction_policy"] == "phase5-book-distraction-v4"
    assert config["target_lock_policy"] == "phase5-shared-target-lock-v2"
    assert config["formal_execution_authorized"] is False
    assert config["readiness_only_authorized"] is True
    assert "docs/evidence/phase5_r1_target_lock_recovery_gate_v2.json" in config[
        "historical_artifacts_frozen"
    ]


def test_v4_manifest_preserves_54_cells_and_binds_target_lock_v2() -> None:
    manifest = _manifest()
    validate_public_manifest(manifest)
    assert manifest["episode_count"] == REAL_EPISODE_COUNT == 54
    assert tuple(manifest["required_metrics"]) == REAL_REQUIRED_METRICS_V5
    assert len(REAL_REQUIRED_METRICS_V5) == 64
    assert {row["target_lock_policy"] for row in manifest["episodes"]} == {
        "phase5-shared-target-lock-v2"
    }
    assert [row["panel"] for row in manifest["episodes"][:3]] == [
        "r1_stable",
        "r1_stable",
        "r1_stable",
    ]
    serialized = json.dumps(manifest, sort_keys=True)
    for forbidden in (
        '"start_pose"',
        '"target_point"',
        '"anchor_id"',
        '"objectId"',
        "Book|",
        "Cup|",
        "CoffeeMachine|",
        "TeleportFull",
        "PlaceObjectAtPoint",
    ):
        assert forbidden not in serialized


def test_v4_readiness_joins_twelve_runtimes_without_starting_thor() -> None:
    config = _config()
    readiness = _executor().build_readiness(config=config, manifest=_manifest())
    assert readiness["readiness_version"] == "phase5-real-thor-formal-readiness-v4"
    assert readiness["executor_version"] == "phase5-real-thor-formal-executor-v4"
    assert readiness["readiness_passed"] is True
    assert readiness["unique_runtime_count"] == 12
    assert readiness["formal_execution_authorized"] is False
    assert readiness["private_runtime_material_serialized"] is False


def _valid_audit_fixture(temporary_dir: str) -> tuple[dict, dict, Path]:
    episode = _manifest()["episodes"][0]
    summary = {key: 0 for key in REAL_REQUIRED_METRICS_V5}
    summary.update(
        {
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
            "invalid_action_count": 1,
            "failed_interaction_count": 1,
            "invalid_planner_decision_count": 0,
            "intervention_count": 0,
            "intervention_failure_count": 0,
            "task_progress": {},
        }
    )
    episode_dir = Path(temporary_dir)
    (episode_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "included_in_formal_aggregate": True,
                "evidence_status": "formal_acceptance_candidate",
                "working_tree_dirty": False,
                "code_revision": "f" * 40,
            }
        ),
        encoding="utf-8",
    )
    (episode_dir / "setup.jsonl").write_text("{}\n", encoding="utf-8")
    (episode_dir / "episode.jsonl").write_text("{}\n", encoding="utf-8")
    (episode_dir / "evaluator_setup.jsonl").write_text("{}\n", encoding="utf-8")
    return episode, summary, episode_dir


def test_v4_legal_native_failure_is_performance_not_integrity() -> None:
    executor = _executor()
    with tempfile.TemporaryDirectory() as temporary_dir:
        episode, summary, episode_dir = _valid_audit_fixture(temporary_dir)
        errors = executor.audit_episode(
            episode=episode,
            summary=summary,
            episode_dir=episode_dir,
            expected_code_revision="f" * 40,
        )
    assert errors == []


def test_v4_invalid_planner_decision_remains_integrity_failure() -> None:
    executor = _executor()
    with tempfile.TemporaryDirectory() as temporary_dir:
        episode, summary, episode_dir = _valid_audit_fixture(temporary_dir)
        summary["invalid_planner_decision_count"] = 1
        errors = executor.audit_episode(
            episode=episode,
            summary=summary,
            episode_dir=episode_dir,
            expected_code_revision="f" * 40,
        )
    assert "integrity_counter:invalid_planner_decision_count" in errors


def test_v4_terminal_target_lock_failure_is_a_task_outcome() -> None:
    executor = _executor()
    with tempfile.TemporaryDirectory() as temporary_dir:
        episode, summary, episode_dir = _valid_audit_fixture(temporary_dir)
        summary["success"] = False
        summary["target_lock_terminal_failure_count"] = 1
        summary["target_lock_failed_reason"] = "bounded_terminal_failure"
        errors = executor.audit_episode(
            episode=episode,
            summary=summary,
            episode_dir=episode_dir,
            expected_code_revision="f" * 40,
        )
    assert errors == []

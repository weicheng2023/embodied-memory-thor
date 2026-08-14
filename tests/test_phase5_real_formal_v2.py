from __future__ import annotations

import importlib.util
import json
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest

from embodied_memory_thor.phase5.formal_v2 import (
    REAL_EPISODE_COUNT,
    REAL_MANIFEST_SCHEMA_VERSION,
    REAL_METRIC_SCHEMA_VERSION,
    REAL_REQUIRED_METRICS,
    FormalManifestError,
    build_public_manifest,
    collect_public_runtime_bindings,
    validate_precommit,
    validate_public_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_real_formal_pilot_v2.json"


def _module() -> object:
    path = ROOT / "scripts" / "run_phase5_real_formal_pilot_v2.py"
    spec = importlib.util.spec_from_file_location("phase5_real_formal_v2_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _manifest() -> dict:
    config = _config()
    bindings = collect_public_runtime_bindings(config, root=ROOT)
    return build_public_manifest(
        config,
        code_revision="a" * 40,
        bindings=bindings,
    )


def test_precommit_is_readiness_only_and_hash_freezes_prerequisites() -> None:
    config = _config()
    validate_precommit(config, root=ROOT)
    assert config["formal_execution_authorized"] is False
    assert config["readiness_only_authorized"] is True
    assert config["episode_count"] == 54
    assert config["max_steps_per_episode"] == 2048
    assert config["variants"] == [
        "no_memory",
        "short_memory_k2",
        "object_memory",
    ]
    assert config["panels"][0]["configuration_ids"] == config["panels"][2][
        "configuration_ids"
    ]


def test_public_manifest_has_exact_matched_54_cells_and_no_private_start() -> None:
    manifest = _manifest()
    assert manifest["manifest_schema_version"] == REAL_MANIFEST_SCHEMA_VERSION
    assert manifest["metric_schema_version"] == REAL_METRIC_SCHEMA_VERSION
    assert manifest["episode_count"] == REAL_EPISODE_COUNT == 54
    assert len(manifest["episodes"]) == 54
    assert [row["episode_index"] for row in manifest["episodes"]] == list(
        range(1, 55)
    )
    assert [row["panel"] for row in manifest["episodes"][::18]] == [
        "r1_stable",
        "r2_stable",
        "r1_stale",
    ]
    for start in range(0, 54, 3):
        cell = manifest["episodes"][start : start + 3]
        assert [row["memory"] for row in cell] == [
            "no_memory",
            "short_memory_k2",
            "object_memory",
        ]
        assert len({row["configuration_id"] for row in cell}) == 1
        assert len({row["search_route_id"] for row in cell}) == 1
    serialized = json.dumps(manifest, sort_keys=True)
    for forbidden in (
        '"start_pose"',
        '"target_point"',
        '"anchor_id"',
        '"objectId"',
        '"private_registry"',
        "Book|",
        "Cup|",
        "CoffeeMachine|",
        "PlaceObjectAtPoint",
        "TeleportFull",
    ):
        assert forbidden not in serialized


def test_manifest_digest_and_private_boundary_fail_closed() -> None:
    manifest = _manifest()
    validate_public_manifest(manifest)
    tampered = deepcopy(manifest)
    tampered["episodes"][0]["start_pose"] = {"x": 1.0}
    with pytest.raises(FormalManifestError):
        validate_public_manifest(tampered)
    tampered = deepcopy(manifest)
    tampered["episodes"][0]["memory"] = "object_memory"
    with pytest.raises(FormalManifestError):
        validate_public_manifest(tampered)


def test_metric_v3_requires_entry_recovery_and_intervention_integrity() -> None:
    for key in (
        "stale_record_recovery_count",
        "intervention_count",
        "intervention_failure_count",
        "shared_search_entry_recovery_policy",
        "shared_search_entry_recovery_action_limit",
        "shared_search_entry_departure_action_count",
        "shared_search_entry_recovery_action_count",
        "shared_search_entry_recovery_pending_action_count",
        "shared_search_entry_recovery_record_failure_count",
    ):
        assert key in REAL_REQUIRED_METRICS
    assert len(REAL_REQUIRED_METRICS) == len(set(REAL_REQUIRED_METRICS))


def test_all_twelve_private_runtimes_join_without_serializing_private_data() -> None:
    module = _module()
    config = _config()
    manifest = _manifest()
    readiness = module.build_readiness(  # type: ignore[attr-defined]
        config=config, manifest=manifest
    )
    assert readiness["readiness_passed"] is True
    assert readiness["unique_runtime_count"] == 12
    assert readiness["private_runtime_join_passed"] is True
    assert readiness["private_runtime_material_serialized"] is False
    serialized = json.dumps(readiness, sort_keys=True)
    for forbidden in (
        '"start_pose"',
        '"target_point"',
        '"anchor_id"',
        '"objectId"',
        "Book|",
        "Cup|",
        "CoffeeMachine|",
        "PlaceObjectAtPoint",
        "TeleportFull",
    ):
        assert forbidden not in serialized


def _valid_failed_outcome_summary(episode: dict) -> dict:
    summary = {key: 0 for key in REAL_REQUIRED_METRICS}
    summary.update(
        {
            "success": False,
            "failure_reason": "max_steps_exceeded",
            "steps": episode["max_steps"],
            "failure_taxonomy": {},
            "information_boundary_passed": True,
            "setup_completed": True,
            "setup_failure_reason": "",
            "included_in_formal_aggregate": True,
            "evidence_status": "formal_acceptance_candidate",
            "shared_search_action_sequence_digest": episode[
                "search_route_action_sequence_digest"
            ],
            "shared_search_route_id": episode["search_route_id"],
            "shared_subgoal_action_sequence_digest": episode.get(
                "subgoal_route_action_sequence_digest"
            ),
            "shared_subgoal_route_id": episode.get("subgoal_route_id"),
            "shared_search_entry_recovery_policy": (
                "phase5-shared-search-entry-recovery-v1"
            ),
            "shared_search_entry_recovery_action_limit": 64,
            "short_memory_evicted_before_reacquisition": False,
            "task_progress": {"protocol_violations": []},
        }
    )
    return summary


def test_audit_separates_valid_task_failure_from_integrity_failure() -> None:
    module = _module()
    episode = next(
        row for row in _manifest()["episodes"]
        if row["panel"] == "r2_stable" and row["memory"] == "no_memory"
    )
    summary = _valid_failed_outcome_summary(episode)
    with tempfile.TemporaryDirectory() as temporary_dir:
        root = Path(temporary_dir)
        (root / "setup.jsonl").write_text("{}\n", encoding="utf-8")
        (root / "episode.jsonl").write_text("{}\n", encoding="utf-8")
        (root / "evaluator_setup.jsonl").write_text("{}\n", encoding="utf-8")
        (root / "run_manifest.json").write_text(
            json.dumps(
                {
                    "included_in_formal_aggregate": True,
                    "evidence_status": "formal_acceptance_candidate",
                    "working_tree_dirty": False,
                    "code_revision": "a" * 40,
                }
            ),
            encoding="utf-8",
        )
        assert module.audit_episode(  # type: ignore[attr-defined]
            episode=episode,
            summary=summary,
            episode_dir=root,
            expected_code_revision="a" * 40,
        ) == []
        (root / "episode.jsonl").write_text(
            json.dumps({"target_point": {"x": 1.0}}) + "\n",
            encoding="utf-8",
        )
        errors = module.audit_episode(  # type: ignore[attr-defined]
            episode=episode,
            summary=summary,
            episode_dir=root,
            expected_code_revision="a" * 40,
        )
        assert any(error.startswith("ordinary_forbidden_key:") for error in errors)


def test_execute_gate_fails_before_creating_output() -> None:
    module = _module()
    with tempfile.TemporaryDirectory() as temporary_dir:
        output = Path(temporary_dir) / "formal"
        with pytest.raises(ValueError, match="not authorized"):
            module.prepare_run(  # type: ignore[attr-defined]
                config_path=CONFIG,
                output_dir=output,
                execute_requested=True,
            )
        assert not output.exists()

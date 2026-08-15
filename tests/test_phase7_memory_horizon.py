from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase4.runner import ThorEpisodeConfig
from embodied_memory_thor.phase4.spatial_memory import (
    ThorObjectMemory,
    ThorShortMemory,
    build_thor_memory,
)
from embodied_memory_thor.phase5.anchors import stable_digest
from embodied_memory_thor.phase7.holdout import validate_public_artifact
from embodied_memory_thor.phase7.recent_memory import (
    PHASE7B_RECENT_CAPACITIES,
    PHASE7B_RECENT_MEMORY_VERSION,
    PHASE7B_VARIANTS,
    Phase7BThorEpisodeConfig,
    RecentObservationMemory,
    build_phase7b_memory,
    recent_capacity,
)


def _observation(*object_types: str) -> dict[str, object]:
    return {
        "agent": {
            "position": {"x": 0.0, "y": 0.9, "z": 0.0},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
            "cameraHorizon": 0.0,
        },
        "objects": [
            {
                "objectId": f"{object_type}|fixture",
                "objectType": object_type,
                "visible": True,
                "position": {"x": 1.0, "y": 1.0, "z": 1.0},
            }
            for object_type in object_types
        ],
    }


def _script_module(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / "phase7" / filename
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recent_k2_matches_historical_phase5_observable_semantics() -> None:
    historical = ThorShortMemory(k=2)
    successor = RecentObservationMemory(2)
    observations = [
        _observation("Book", "Desk"),
        _observation("Chair"),
        _observation("Floor"),
        _observation("Book"),
    ]
    for step, observation in enumerate(observations):
        observation_id = f"observation:{step}"
        assert historical.observe(
            observation, step=step, observation_id=observation_id
        ) == successor.observe(
            observation, step=step, observation_id=observation_id
        )
        assert historical.retrieve("Book") == successor.retrieve("Book")
        assert historical.snapshot() == successor.snapshot()


def test_recent_capacity_crosses_exact_observation_horizon() -> None:
    k4 = RecentObservationMemory(4)
    k8 = RecentObservationMemory(8)
    for memory in (k4, k8):
        memory.observe(_observation("Book"), step=0, observation_id="observation:0")
    for step in range(1, 4):
        for memory in (k4, k8):
            memory.observe(
                _observation("Chair"),
                step=step,
                observation_id=f"observation:{step}",
            )
    assert k4.retrieve("Book")
    assert k8.retrieve("Book")

    for memory in (k4, k8):
        memory.observe(
            _observation("Floor"), step=4, observation_id="observation:4"
        )
    assert k4.retrieve("Book") == []
    assert k8.retrieve("Book")


def test_phase7b_factory_is_additive_and_phase5_constructor_is_unchanged() -> None:
    assert PHASE7B_RECENT_MEMORY_VERSION == "phase7b-recent-observation-memory-v1"
    assert PHASE7B_RECENT_CAPACITIES == {
        "recent_memory_k2": 2,
        "recent_memory_k4": 4,
        "recent_memory_k8": 8,
    }
    for variant, capacity in PHASE7B_RECENT_CAPACITIES.items():
        provider = build_phase7b_memory(variant)
        assert isinstance(provider, RecentObservationMemory)
        assert provider.k == capacity
        assert recent_capacity(variant) == capacity
    assert build_phase7b_memory("no_memory").kind == "none"
    assert isinstance(build_phase7b_memory("object_memory"), ThorObjectMemory)

    historical = build_thor_memory("short_memory_k2")
    assert type(historical) is ThorShortMemory
    assert historical.k == 2
    with pytest.raises(ValueError, match="unsupported Phase 4 memory kind"):
        build_thor_memory("recent_memory_k2")


def test_phase7b_config_accepts_labels_without_changing_phase4_validation() -> None:
    for variant in PHASE7B_VARIANTS:
        Phase7BThorEpisodeConfig(memory=variant).validate()
    with pytest.raises(ValueError, match="unsupported memory mode"):
        ThorEpisodeConfig(memory="recent_memory_k4").validate()


def test_phase7b_manifest_is_frozen_hash_bound_and_public() -> None:
    module = _script_module("run_memory_horizon.py", "phase7b_runner")
    manifest_path = ROOT / "configs" / "phase7" / "memory_horizon_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    module.validate_memory_horizon_manifest(manifest)
    module.validate_bound_sources(manifest)
    assert tuple(manifest["variants"]) == PHASE7B_VARIANTS
    assert manifest["expected_episode_count"] == 30
    assert manifest["prior_episode_reuse"] is False
    assert manifest["optional_persistent_snapshot_memory_used"] is False
    validate_public_artifact(manifest)

    for path_key, hash_key in (
        ("configuration_source", "configuration_source_sha256"),
        ("evaluator_registry", "evaluator_registry_sha256"),
        ("route_registry", "route_registry_sha256"),
    ):
        path = ROOT / manifest[path_key]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest[hash_key]
    digest_payload = dict(manifest)
    expected_digest = digest_payload.pop("manifest_digest")
    assert stable_digest(digest_payload) == expected_digest


def test_retention_checkpoint_reduces_target_identity_to_public_scalars(
    tmp_path: Path,
) -> None:
    module = _script_module("run_memory_horizon.py", "phase7b_retention")
    target_id = "Book|secret-target"
    rows = [
        {
            "step": 1,
            "planner_input": {
                "request": {
                    "step": 1,
                    "task_stage": "controlled_distraction_v4_1_RotateRight",
                    "retrieved_memory": [],
                }
            },
            "environment_feedback": {"memory_before": {"kind": "short", "k": 4}},
        },
        {
            "step": 5,
            "planner_input": {
                "request": {
                    "step": 5,
                    "task_stage": "reacquire_book",
                    "retrieved_memory": [
                        {
                            "object_id": target_id,
                            "object_type": "Book",
                            "last_seen_step": 0,
                        }
                    ],
                }
            },
            "environment_feedback": {
                "memory_before": {
                    "kind": "short",
                    "k": 4,
                    "observation_ids": ["o1", "o2", "o3", "o4"],
                }
            },
        },
    ]
    trace = tmp_path / "episode.jsonl"
    trace.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    checkpoint = module.retention_checkpoint(trace, target_object_id=target_id)
    assert checkpoint["retention_checkpoint_found"] is True
    assert checkpoint["target_record_present_at_reacquisition"] is True
    assert checkpoint["target_record_age_actions_at_reacquisition"] == 5
    assert checkpoint["recent_capacity_at_reacquisition"] == 4
    assert checkpoint["recent_observation_count_at_reacquisition"] == 4
    assert target_id not in json.dumps(checkpoint)
    validate_public_artifact(checkpoint)


def test_phase7b_compact_row_uses_frozen_budgets() -> None:
    module = _script_module("run_memory_horizon.py", "phase7b_compact")
    row = module.compact_result_row(
        episode_index=1,
        configuration_id="fixture",
        summary={
            "scene": "FloorPlan999",
            "memory": "recent_memory_k4",
            "success": True,
            "failure_reason": "",
            "steps": 20,
        },
        retention={
            "retention_checkpoint_found": True,
            "target_record_present_at_reacquisition": True,
        },
        integrity_errors=[],
        budgets=[18, 72, 2048],
    )
    assert row["recent_capacity"] == 4
    assert row["success_at_18"] is False
    assert row["success_at_72"] is True
    assert row["success_at_2048"] is True
    validate_public_artifact(row)


def test_phase7b_aggregator_requires_fresh_ordered_quintets() -> None:
    module = _script_module("aggregate_memory_horizon.py", "phase7b_aggregate")
    rows = []
    steps_by_variant = {
        "no_memory": 10,
        "recent_memory_k2": 10,
        "recent_memory_k4": 9,
        "recent_memory_k8": 9,
        "object_memory": 8,
    }
    retained = {
        "no_memory": False,
        "recent_memory_k2": False,
        "recent_memory_k4": True,
        "recent_memory_k8": True,
        "object_memory": True,
    }
    for configuration_index in range(6):
        for variant in PHASE7B_VARIANTS:
            steps = steps_by_variant[variant]
            rows.append(
                {
                    "configuration_id": f"configuration_{configuration_index}",
                    "memory": variant,
                    "success": True,
                    "success_at_18": True,
                    "success_at_72": True,
                    "success_at_2048": True,
                    "steps": steps,
                    "target_reacquisition_action_count": steps - 2,
                    "translation_action_count": 0,
                    "translation_distance_meters": 0.0,
                    "search_rotation_count": 0,
                    "repeated_viewpoint_visit_count": 2,
                    "memory_guided_action_count": int(retained[variant]),
                    "memory_retrieval_count": 1,
                    "target_record_present_at_reacquisition": retained[variant],
                    "target_record_age_actions_at_reacquisition": (
                        4 if retained[variant] else None
                    ),
                    "shared_search_entry_recovery_action_count": 0,
                    "shared_search_coverage_action_count": 0,
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
    assert result["target_retention_counts"]["recent_memory_k2"]["present"] == 0
    assert result["target_retention_counts"]["recent_memory_k4"]["present"] == 6
    assert result["capacity_curve"][0]["k"] == 2
    paired = result["metrics"]["steps"]["paired_differences"]
    assert paired["object_memory_minus_recent_memory_k8"]["differences"] == [
        -1,
        -1,
        -1,
        -1,
        -1,
        -1,
    ]

from __future__ import annotations

import importlib.util
import hashlib
import json
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest

from embodied_memory_thor.phase5.formal_v2 import (
    REAL_EPISODE_COUNT,
    REAL_MANIFEST_SCHEMA_VERSION_V3,
    REAL_METRIC_SCHEMA_VERSION_V4,
    REAL_PROTOCOL_VERSION_V3,
    REAL_REQUIRED_METRICS_V4,
    build_public_manifest,
    collect_public_runtime_bindings,
    validate_precommit,
    validate_public_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_real_formal_pilot_v3.json"
AUTHORIZATION = ROOT / "configs" / "phase5_real_formal_execution_v3.json"
READINESS_EVIDENCE = (
    ROOT / "docs" / "evidence" / "phase5_real_formal_readiness_v3.json"
)
INVALIDATED_STOP_EVIDENCE = (
    ROOT / "docs" / "evidence" / "phase5_real_formal_pilot_v3_invalidated_stop.json"
)
COVERAGE_EVIDENCE = (
    ROOT / "docs" / "evidence" / "phase5_r1_distraction_coverage_gate_v1.json"
)


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _manifest() -> dict:
    config = _config()
    bindings = collect_public_runtime_bindings(config, root=ROOT)
    return build_public_manifest(
        config,
        code_revision="d" * 40,
        bindings=bindings,
    )


def _executor() -> object:
    path = ROOT / "scripts" / "run_phase5_real_formal_pilot_v2.py"
    spec = importlib.util.spec_from_file_location("phase5_formal_v3_shared", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _authorization_executor() -> object:
    path = ROOT / "scripts" / "run_phase5_real_formal_execution_v3.py"
    spec = importlib.util.spec_from_file_location("phase5_formal_v3_authorized", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v3_precommit_contract_is_readiness_only_and_historical_hash_is_frozen() -> None:
    config = _config()
    validate_precommit(config, root=ROOT, check_hashes=False)
    assert config["manifest_schema_version"] == REAL_MANIFEST_SCHEMA_VERSION_V3
    assert config["protocol_version"] == REAL_PROTOCOL_VERSION_V3
    assert config["metric_schema_version"] == REAL_METRIC_SCHEMA_VERSION_V4
    assert config["book_distraction_policy"] == "phase5-book-distraction-v4"
    assert config["formal_execution_authorized"] is False
    assert config["readiness_only_authorized"] is True
    assert "docs/evidence/phase5_r1_distraction_coverage_gate_v1.json" in config[
        "historical_artifacts_frozen"
    ]
    changed = [
        relative
        for relative, expected in config["historical_artifacts_frozen"].items()
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected
    ]
    assert changed == [
        "src/embodied_memory_thor/phase4/runner.py",
        "src/embodied_memory_thor/phase5/formal_v2.py",
        "scripts/run_phase5_real_formal_pilot_v2.py",
    ]


def test_v3_manifest_keeps_54_cells_and_binds_task_policies() -> None:
    manifest = _manifest()
    validate_public_manifest(manifest)
    assert manifest["episode_count"] == REAL_EPISODE_COUNT == 54
    assert tuple(manifest["required_metrics"]) == REAL_REQUIRED_METRICS_V4
    assert len(REAL_REQUIRED_METRICS_V4) == len(set(REAL_REQUIRED_METRICS_V4))
    r1 = [row for row in manifest["episodes"] if row["task"] == "thor_book_reacquire_k2"]
    r2 = [
        row
        for row in manifest["episodes"]
        if row["task"] == "thor_cup_after_coffee_subgoal"
    ]
    assert len(r1) == 36 and len(r2) == 18
    assert {row["book_distraction_policy"] for row in r1} == {
        "phase5-book-distraction-v4"
    }
    assert {row["book_distraction_policy"] for row in r2} == {
        "phase5-book-distraction-v1"
    }
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


def test_v3_readiness_joins_twelve_private_runtimes_without_serializing_them() -> None:
    executor = _executor()
    config = _config()
    readiness = executor.build_readiness(  # type: ignore[attr-defined]
        config=config,
        manifest=_manifest(),
    )
    assert readiness["readiness_version"] == "phase5-real-thor-formal-readiness-v3"
    assert readiness["executor_version"] == "phase5-real-thor-formal-executor-v3"
    assert readiness["readiness_passed"] is True
    assert readiness["unique_runtime_count"] == 12
    assert readiness["formal_execution_authorized"] is False
    serialized = json.dumps(readiness, sort_keys=True)
    for forbidden in (
        '"start_pose"',
        '"target_point"',
        '"anchor_id"',
        '"objectId"',
        "TeleportFull",
        "PlaceObjectAtPoint",
    ):
        assert forbidden not in serialized


def test_v3_execute_remains_blocked_after_invalidated_successor_change() -> None:
    executor = _executor()
    with tempfile.TemporaryDirectory() as temporary_dir:
        output = Path(temporary_dir) / "formal-v3"
        with pytest.raises(ValueError, match="historical_artifact"):
            executor.prepare_run(  # type: ignore[attr-defined]
                config_path=CONFIG,
                output_dir=output,
                execute_requested=True,
            )
        assert not output.exists()


def test_v3_public_gate_evidence_is_complete_excluded_and_coordinate_free() -> None:
    evidence = json.loads(COVERAGE_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["passed"] is True
    assert evidence["completed_episode_count"] == 8
    assert evidence["all_targets_hidden_after_template"] is True
    assert evidence["all_information_boundaries_passed"] is True
    assert evidence["included_in_formal_aggregate"] is False
    text = COVERAGE_EVIDENCE.read_text(encoding="utf-8")
    for forbidden in (
        '"x"',
        '"y"',
        '"z"',
        '"objectId"',
        "Book|",
        "TeleportFull",
        "PlaceObjectAtPoint",
    ):
        assert forbidden not in text


def test_v3_wrapper_defaults_to_v3_readiness_config() -> None:
    source = (ROOT / "scripts" / "run_phase5_real_formal_pilot_v3.py").read_text(
        encoding="utf-8"
    )
    assert "phase5_real_formal_pilot_v3.json" in source
    assert "--readiness-only" in source
    assert "--execute" in source


def test_v3_authorization_is_not_reusable_after_successor_source_change() -> None:
    executor = _authorization_executor()
    with pytest.raises(ValueError, match="historical_artifact"):
        executor.load_authorized_config(AUTHORIZATION)


def test_v3_authorization_rejects_tampered_readiness_binding() -> None:
    executor = _authorization_executor()
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    tampered = deepcopy(raw)
    tampered["readiness_manifest_digest"] = "0" * 64
    with tempfile.TemporaryDirectory() as temporary_dir:
        path = Path(temporary_dir) / "tampered.json"
        path.write_text(json.dumps(tampered), encoding="utf-8")
        with pytest.raises(ValueError, match="does not authorize"):
            executor.load_authorized_config(path)


def test_v3_readiness_evidence_is_public_and_execution_disabled() -> None:
    evidence = json.loads(READINESS_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["readiness_passed"] is True
    assert evidence["episode_count"] == REAL_EPISODE_COUNT
    assert evidence["unique_runtime_count"] == 12
    assert evidence["private_runtime_join_passed"] is True
    assert evidence["private_runtime_material_serialized"] is False
    assert evidence["formal_execution_authorized_during_readiness"] is False
    text = READINESS_EVIDENCE.read_text(encoding="utf-8")
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
        assert forbidden not in text


def test_v3_invalidated_stop_is_complete_excluded_and_public() -> None:
    evidence = json.loads(INVALIDATED_STOP_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["completed_episode_count"] == 15
    assert evidence["expected_episode_count"] == REAL_EPISODE_COUNT
    assert evidence["matrix_complete"] is False
    assert evidence["integrity_valid"] is False
    assert evidence["included_in_formal_aggregate"] is False
    assert evidence["partial_matrix_reusable"] is False
    assert evidence["stop_cell"]["information_boundary_passed"] is True
    assert evidence["stop_cell"]["invalid_action_count"] == 2042
    assert evidence["failure_classification"] == (
        "shared_target_lock_interaction_recovery_defect"
    )
    text = INVALIDATED_STOP_EVIDENCE.read_text(encoding="utf-8")
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
        assert forbidden not in text

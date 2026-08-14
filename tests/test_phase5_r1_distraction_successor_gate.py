from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from embodied_memory_thor.phase4.runner import ThorEpisodeConfig
from embodied_memory_thor.phase4.task import PHASE5_BOOK_DISTRACTION_POLICY_V2
from embodied_memory_thor.phase4.task import PHASE5_BOOK_DISTRACTION_POLICY_V3
from embodied_memory_thor.phase4.task import PHASE5_BOOK_DISTRACTION_POLICY_V4


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_r1_distraction_successor_gate_v1.json"
CONFIG_V2 = ROOT / "configs" / "phase5_r1_distraction_successor_gate_v2.json"
STOP_EVIDENCE = (
    ROOT / "docs" / "evidence" / "phase5_r1_distraction_successor_gate_v1_stop.json"
)
COVERAGE_CONFIG = ROOT / "configs" / "phase5_r1_distraction_coverage_gate_v1.json"
V2_STOP_EVIDENCE = (
    ROOT / "docs" / "evidence" / "phase5_r1_distraction_successor_gate_v2_stop.json"
)


def _module() -> object:
    path = ROOT / "scripts" / "run_phase5_r1_distraction_successor_gate.py"
    spec = importlib.util.spec_from_file_location("phase5_r1_distraction_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate_is_fixed_target_independent_and_excluded() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    _module().validate_gate_config(config)  # type: ignore[attr-defined]
    assert config["book_distraction_policy"] == PHASE5_BOOK_DISTRACTION_POLICY_V2
    assert config["expected_actions"] == [
        "RotateRight",
        "RotateRight",
        "LookDown",
        "LookUp",
    ]
    assert config["max_steps"] == 4
    assert config["included_in_formal_aggregate"] is False
    serialized = CONFIG.read_text(encoding="utf-8")
    for forbidden in (
        '"target_point"',
        '"objectId"',
        '"anchor_id"',
        '"start_pose"',
        "Book|",
        "TeleportFull",
        "PlaceObjectAtPoint",
    ):
        assert forbidden not in serialized


def test_runner_accepts_successor_only_for_r1() -> None:
    ThorEpisodeConfig(
        task="thor_book_reacquire_k2",
        book_distraction_policy=PHASE5_BOOK_DISTRACTION_POLICY_V2,
    ).validate()
    config = ThorEpisodeConfig(
        task="thor_cup_after_coffee_subgoal",
        book_distraction_policy=PHASE5_BOOK_DISTRACTION_POLICY_V2,
    )
    try:
        config.validate()
    except ValueError as exc:
        assert "only" in str(exc)
    else:
        raise AssertionError("R2 accepted the R1-only distraction successor")


def test_horizon_independent_successor_is_fixed_excluded_and_stop_bound() -> None:
    config = json.loads(CONFIG_V2.read_text(encoding="utf-8"))
    _module().validate_gate_config(config)  # type: ignore[attr-defined]
    assert config["book_distraction_policy"] == PHASE5_BOOK_DISTRACTION_POLICY_V3
    assert config["expected_actions"] == ["RotateRight", "RotateRight", "Pass"]
    assert config["max_steps"] == 3
    assert config["included_in_formal_aggregate"] is False
    evidence = json.loads(STOP_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["passed"] is False
    assert evidence["episode_reuse_allowed"] is False
    assert evidence["failure_class"] == "relative_horizon_limit_failure"
    serialized = CONFIG_V2.read_text(encoding="utf-8")
    for forbidden in (
        '"target_point"',
        '"objectId"',
        '"anchor_id"',
        '"start_pose"',
        "Book|",
        "TeleportFull",
        "PlaceObjectAtPoint",
    ):
        assert forbidden not in serialized


def test_runner_accepts_horizon_independent_successor_for_r1() -> None:
    ThorEpisodeConfig(
        task="thor_book_reacquire_k2",
        book_distraction_policy=PHASE5_BOOK_DISTRACTION_POLICY_V3,
    ).validate()


def test_six_configuration_coverage_gate_is_fixed_and_excluded() -> None:
    config = json.loads(COVERAGE_CONFIG.read_text(encoding="utf-8"))
    _module().validate_coverage_config(config)  # type: ignore[attr-defined]
    assert config["book_distraction_policy"] == PHASE5_BOOK_DISTRACTION_POLICY_V4
    assert config["total_episode_count"] == 8
    assert len(config["configuration_order"]) == 6
    floorplan303 = config["configuration_order"][2]
    assert floorplan303["variants"] == [
        "no_memory",
        "short_memory_k2",
        "object_memory",
    ]
    evidence = json.loads(V2_STOP_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["passed"] is False
    assert evidence["same_initial_target_visible_after_half_turn"] is True
    serialized = COVERAGE_CONFIG.read_text(encoding="utf-8")
    for forbidden in (
        '"target_point"',
        '"objectId"',
        '"anchor_id"',
        '"start_pose"',
        "Book|",
        "TeleportFull",
        "PlaceObjectAtPoint",
    ):
        assert forbidden not in serialized


def test_gate_source_has_no_target_conditioned_action_selection() -> None:
    source = (
        ROOT / "scripts" / "run_phase5_r1_distraction_successor_gate.py"
    ).read_text(encoding="utf-8")
    assert "GetSpawnCoordinatesAboveReceptacle" not in source
    assert "reachable_positions" in source  # leak audit only
    assert "memory.retrieve" not in source
    assert "target_point" in source  # leak audit only

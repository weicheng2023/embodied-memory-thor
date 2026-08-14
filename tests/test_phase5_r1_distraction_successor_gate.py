from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from embodied_memory_thor.phase4.runner import ThorEpisodeConfig
from embodied_memory_thor.phase4.task import PHASE5_BOOK_DISTRACTION_POLICY_V2


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_r1_distraction_successor_gate_v1.json"


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


def test_gate_source_has_no_target_conditioned_action_selection() -> None:
    source = (
        ROOT / "scripts" / "run_phase5_r1_distraction_successor_gate.py"
    ).read_text(encoding="utf-8")
    assert "GetSpawnCoordinatesAboveReceptacle" not in source
    assert "reachable_positions" in source  # leak audit only
    assert "memory.retrieve" not in source
    assert "target_point" in source  # leak audit only

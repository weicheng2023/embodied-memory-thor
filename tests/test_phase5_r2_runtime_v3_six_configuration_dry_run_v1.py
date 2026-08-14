from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (
    ROOT / "configs" / "phase5_r2_runtime_v3_six_configuration_dry_run_v1.json"
)
EXPECTED_ORDER = [
    "FloorPlan3_R2_fixed_start_001",
    "FloorPlan4_R2_fixed_start_001",
    "FloorPlan6_R2_fixed_start_001",
    "FloorPlan7_R2_fixed_start_001",
    "FloorPlan12_R2_fixed_start_001",
    "FloorPlan17_R2_fixed_start_001",
]
VARIANTS = ["no_memory", "short_memory_k2", "object_memory"]


def _module() -> object:
    path = ROOT / "scripts" / "run_phase5_r2_runtime_v3_six_configuration_dry_run_v1.py"
    spec = importlib.util.spec_from_file_location("phase5_r2_runtime_v3_dry_run_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dry_run_is_fresh_excluded_fixed_6_by_3_matrix() -> None:
    module = _module()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    module.validate_dry_run_config(config)  # type: ignore[attr-defined]
    assert config["configuration_order"] == EXPECTED_ORDER
    assert config["variants"] == VARIANTS
    assert config["expected_cell_count"] == 18
    assert config["max_steps_per_episode"] == 2048
    assert config["included_in_formal_aggregate"] is False
    assert config["formal_execution_authorized"] is False
    assert config["episode_reuse_allowed"] is False


def test_dry_run_freezes_runtime_integration_evidence_and_execution_sources() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    for relative, expected in config["historical_artifacts_frozen"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_all_six_runtime_v3_configurations_load_in_declared_order() -> None:
    from embodied_memory_thor.phase5.frozen_r2_v3 import load_frozen_r2_runtime_v3

    scenes = []
    for configuration_id in EXPECTED_ORDER:
        runtime = load_frozen_r2_runtime_v3(configuration_id)
        scenes.append(runtime.configuration.scene)
        assert runtime.subgoal_route.scene == runtime.configuration.scene
        assert runtime.fallback_route.scene == runtime.configuration.scene
    assert scenes == ["FloorPlan3", "FloorPlan4", "FloorPlan6", "FloorPlan7", "FloorPlan12", "FloorPlan17"]


def test_cell_order_is_configuration_major_and_stops_fail_closed() -> None:
    cells = [
        (configuration_id, variant)
        for configuration_id in EXPECTED_ORDER
        for variant in VARIANTS
    ]
    assert len(cells) == 18
    assert cells[:4] == [
        (EXPECTED_ORDER[0], "no_memory"),
        (EXPECTED_ORDER[0], "short_memory_k2"),
        (EXPECTED_ORDER[0], "object_memory"),
        (EXPECTED_ORDER[1], "no_memory"),
    ]
    source = (
        ROOT / "scripts" / "run_phase5_r2_runtime_v3_six_configuration_dry_run_v1.py"
    ).read_text(encoding="utf-8")
    assert source.index("for configuration_id in EXPECTED_CONFIGURATION_ORDER:") < source.index(
        "for variant in PHASE5_VARIANTS:"
    )
    assert "if errors:" in source
    assert "break" in source


def test_dry_run_uses_one_shared_runtime_per_configuration_and_no_images() -> None:
    source = (
        ROOT / "scripts" / "run_phase5_r2_runtime_v3_six_configuration_dry_run_v1.py"
    ).read_text(encoding="utf-8")
    assert source.index("runtime = load_frozen_r2_runtime_v3(configuration_id)") < source.index(
        "for variant in PHASE5_VARIANTS:"
    )
    assert "memory=variant" in source
    assert "search_route=runtime.fallback_route" in source
    assert "subgoal_route=runtime.subgoal_route" in source
    assert "evaluator_setup=runtime.configuration" in source
    assert "save_frames=False" in source
    assert "save_evaluator_debug=False" in source


def test_public_dry_run_material_contains_no_private_runtime_data() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    for forbidden in ('"x"', '"y"', '"z"', "Cup|", "CoffeeMachine|", "objectId", "TeleportFull", "reachable_positions"):
        assert forbidden not in text

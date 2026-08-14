from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "phase5_r2_runtime_v3_integration_probe_v1.json"


def _module() -> object:
    path = ROOT / "scripts" / "run_phase5_r2_runtime_v3_integration_probe_v1.py"
    spec = importlib.util.spec_from_file_location("phase5_r2_runtime_v3_probe_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_is_excluded_fixed_order_and_public_safe() -> None:
    module = _module()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    module.validate_probe_config(config)  # type: ignore[attr-defined]
    assert config["runtime_set_version"] == "phase5-r2-frozen-runtime-set-v3"
    assert config["configuration_id"] == "FloorPlan17_R2_fixed_start_001"
    assert config["variants"] == ["no_memory", "short_memory_k2", "object_memory"]
    assert config["max_steps"] == 2048
    assert config["included_in_formal_aggregate"] is False
    assert config["formal_execution_authorized"] is False
    assert config["episode_reuse_allowed"] is False
    serialized = json.dumps(config, sort_keys=True)
    for forbidden in ('"x"', '"y"', '"z"', "Cup|", "CoffeeMachine|", "objectId", "TeleportFull"):
        assert forbidden not in serialized


def test_probe_freezes_runtime_gate_and_execution_sources() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    for relative, expected in config["historical_artifacts_frozen"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_probe_runtime_binding_matches_floorplan17_v3() -> None:
    from embodied_memory_thor.phase5.frozen_r2_v3 import load_frozen_r2_runtime_v3

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    runtime = load_frozen_r2_runtime_v3(config["configuration_id"])
    public = runtime.configuration.public_reference()
    for key in (
        "scene", "private_configuration_set_digest", "source_qualification_digest",
        "subgoal_route_id", "fallback_route_id",
    ):
        assert str(config[key]) == str(public[key])
    assert runtime.subgoal_route.action_sequence_digest == config[
        "subgoal_route_action_sequence_digest"
    ]
    assert runtime.fallback_route.action_sequence_digest == config[
        "fallback_route_action_sequence_digest"
    ]


def test_probe_loads_runtime_once_before_the_fixed_variant_loop() -> None:
    source = (
        ROOT / "scripts" / "run_phase5_r2_runtime_v3_integration_probe_v1.py"
    ).read_text(encoding="utf-8")
    load_index = source.index("runtime = load_frozen_r2_runtime_v3(CONFIGURATION_ID)")
    loop_index = source.index("for variant in PHASE5_VARIANTS:")
    assert load_index < loop_index
    assert source.count("runtime = load_frozen_r2_runtime_v3(CONFIGURATION_ID)") == 1
    assert "memory=variant" in source
    assert "search_route=runtime.fallback_route" in source
    assert "subgoal_route=runtime.subgoal_route" in source
    assert "evaluator_setup=runtime.configuration" in source


def test_variant_specific_audits_require_k2_eviction_and_object_guidance() -> None:
    source = (
        ROOT / "scripts" / "run_phase5_r2_runtime_v3_integration_probe_v1.py"
    ).read_text(encoding="utf-8")
    assert 'variant == "no_memory"' in source
    assert 'variant == "short_memory_k2"' in source
    assert "short_memory_evicted_before_reacquisition" in source
    assert 'variant == "object_memory"' in source
    assert "memory_retrieval_count" in source
    assert "memory_guided_action_count" in source
    assert "break" in source


def test_ordinary_privacy_walker_rejects_evaluator_keys() -> None:
    module = _module()
    safe = {"planner_input": {"visible_objects": ["Cup"]}}
    leaked = {"planner_input": {"target_cup_object_id": "private"}}
    assert module._walk_forbidden(safe) == []  # type: ignore[attr-defined]
    assert module._walk_forbidden(leaked) == [  # type: ignore[attr-defined]
        "planner_input.target_cup_object_id"
    ]

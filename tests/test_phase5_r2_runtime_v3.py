from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FREEZE_CONFIG = ROOT / "configs" / "phase5_r2_runtime_freeze_v3.json"
PUBLIC_RUNTIME = ROOT / "configs" / "phase5_r2_frozen_runtime_v3.json"
PUBLIC_ROUTES = ROOT / "configs" / "phase5_r2_search_routes_v3.json"
FREEZE_EVIDENCE = ROOT / "docs" / "evidence" / "phase5_r2_runtime_freeze_v3.json"
EXPECTED_ORDER = [
    "FloorPlan3_R2_fixed_start_001",
    "FloorPlan4_R2_fixed_start_001",
    "FloorPlan6_R2_fixed_start_001",
    "FloorPlan7_R2_fixed_start_001",
    "FloorPlan12_R2_fixed_start_001",
    "FloorPlan17_R2_fixed_start_001",
]


def _module() -> object:
    path = ROOT / "scripts" / "freeze_phase5_r2_runtime_v3.py"
    spec = importlib.util.spec_from_file_location("freeze_phase5_r2_runtime_v3_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v3_plan_is_the_single_conservative_replacement() -> None:
    config = json.loads(FREEZE_CONFIG.read_text(encoding="utf-8"))
    assert config["runtime_set_version"] == "phase5-r2-frozen-runtime-set-v3"
    assert config["configuration_order"] == EXPECTED_ORDER
    assert config["excluded_configuration_id"] == "FloorPlan10_R2_fixed_start_001"
    assert config["replacement_configuration_id"] == EXPECTED_ORDER[-1]
    assert config["planner_visible"] is False
    assert config["memory_variants_run"] is False
    assert config["formal_use_allowed"] is False
    assert "FloorPlan10_R2_fixed_start_001" not in config["configuration_order"]


def test_v3_gate_and_all_historical_hashes_are_bound() -> None:
    module = _module()
    config = json.loads(FREEZE_CONFIG.read_text(encoding="utf-8"))
    module.validate_freeze_config(config)  # type: ignore[attr-defined]
    assert "docs/evidence/phase5_r2_floorplan17_production_gate_v1.json" in (
        config["historical_artifacts_frozen"]
    )
    for relative, expected in config["historical_artifacts_frozen"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_v3_public_material_is_action_only_and_has_twelve_routes() -> None:
    module = _module()
    config = json.loads(FREEZE_CONFIG.read_text(encoding="utf-8"))
    rows, routes = module._public_material(config)  # type: ignore[attr-defined]
    assert [row["configuration_id"] for row in rows] == EXPECTED_ORDER
    assert len(routes) == 12
    assert len({route["route_id"] for route in routes}) == 12
    serialized = json.dumps({"rows": rows, "routes": routes}, sort_keys=True)
    for forbidden in ('"x"', '"y"', '"z"', "Cup|", "CoffeeMachine|", "objectId", "TeleportFull"):
        assert forbidden not in serialized


def test_generated_v3_runtime_loads_all_six_with_expected_action_counts() -> None:
    from embodied_memory_thor.phase5.frozen_r2_v3 import load_frozen_r2_runtime_v3

    action_counts = {}
    for configuration_id in EXPECTED_ORDER:
        runtime = load_frozen_r2_runtime_v3(configuration_id)
        action_counts[configuration_id] = (
            runtime.subgoal_route.action_count,
            runtime.fallback_route.action_count,
        )
    assert action_counts == {
        "FloorPlan3_R2_fixed_start_001": (6, 110),
        "FloorPlan4_R2_fixed_start_001": (11, 110),
        "FloorPlan6_R2_fixed_start_001": (13, 403),
        "FloorPlan7_R2_fixed_start_001": (11, 685),
        "FloorPlan12_R2_fixed_start_001": (9, 1367),
        "FloorPlan17_R2_fixed_start_001": (4, 212),
    }


def test_v3_evidence_hashes_the_generated_public_outputs() -> None:
    evidence = json.loads(FREEZE_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["configuration_order"] == EXPECTED_ORDER
    assert evidence["deterministic_second_freeze_matched"] is True
    assert hashlib.sha256(PUBLIC_RUNTIME.read_bytes()).hexdigest() == evidence[
        "public_runtime_registry_sha256"
    ]
    assert hashlib.sha256(PUBLIC_ROUTES.read_bytes()).hexdigest() == evidence[
        "public_route_registry_sha256"
    ]
    runtime = json.loads(PUBLIC_RUNTIME.read_text(encoding="utf-8"))
    assert runtime["private_configuration_set_digest"] == evidence[
        "private_configuration_set_digest"
    ]


def test_v3_public_outputs_do_not_leak_private_runtime_material() -> None:
    public = "\n".join(path.read_text(encoding="utf-8") for path in (
        PUBLIC_RUNTIME, PUBLIC_ROUTES, FREEZE_EVIDENCE,
    ))
    for forbidden in ('"x"', '"y"', '"z"', "Cup|", "CoffeeMachine|", "objectId", "TeleportFull"):
        assert forbidden not in public
    runtime = json.loads(PUBLIC_RUNTIME.read_text(encoding="utf-8"))
    routes = json.loads(PUBLIC_ROUTES.read_text(encoding="utf-8"))
    assert runtime["runtime_set_version"] == "phase5-r2-frozen-runtime-set-v3"
    assert routes["runtime_set_version"] == "phase5-r2-frozen-runtime-set-v3"
    assert [row["configuration_id"] for row in runtime["configurations"]] == EXPECTED_ORDER


def test_v2_runtime_and_routes_remain_byte_frozen() -> None:
    config = json.loads(FREEZE_CONFIG.read_text(encoding="utf-8"))
    frozen = config["historical_artifacts_frozen"]
    for relative in (
        "configs/phase5_r2_frozen_runtime_v2.json",
        "configs/phase5_r2_search_routes_v2.json",
        "docs/evidence/phase5_r2_runtime_freeze_v2.json",
    ):
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == frozen[relative]

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from embodied_memory_thor.phase5.anchors import stable_digest
from embodied_memory_thor.phase5.frozen_r2 import PRIVATE_BOUNDARY


ROOT = Path(__file__).resolve().parents[1]
FREEZE_CONFIG = ROOT / "configs" / "phase5_r2_runtime_freeze_v2.json"
FREEZE_EVIDENCE = ROOT / "docs" / "evidence" / "phase5_r2_runtime_freeze_v2.json"


def _module() -> object:
    path = ROOT / "scripts" / "freeze_phase5_r2_runtime_v2.py"
    spec = importlib.util.spec_from_file_location("freeze_phase5_r2_runtime_v2_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v2_freeze_plan_has_six_ordered_qualified_sources_and_frozen_hashes() -> None:
    config = json.loads(FREEZE_CONFIG.read_text(encoding="utf-8"))
    assert config["runtime_set_version"] == "phase5-r2-frozen-runtime-set-v2"
    assert config["configuration_order"] == [
        "FloorPlan3_R2_fixed_start_001",
        "FloorPlan4_R2_fixed_start_001",
        "FloorPlan6_R2_fixed_start_001",
        "FloorPlan7_R2_fixed_start_001",
        "FloorPlan10_R2_fixed_start_001",
        "FloorPlan12_R2_fixed_start_001",
    ]
    assert config["planner_visible"] is False
    assert config["memory_variants_run"] is False
    assert config["formal_use_allowed"] is False
    for relative, expected in config["historical_artifacts_frozen"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_public_material_contains_twelve_valid_coordinate_free_routes() -> None:
    module = _module()
    config = json.loads(FREEZE_CONFIG.read_text(encoding="utf-8"))
    module.validate_freeze_config(config)  # type: ignore[attr-defined]
    rows, routes = module._public_material(config)  # type: ignore[attr-defined]
    assert len(rows) == 6
    assert len(routes) == 12
    assert len({row["configuration_id"] for row in rows}) == 6
    assert len({route["route_id"] for route in routes}) == 12
    serialized = json.dumps({"rows": rows, "routes": routes}, sort_keys=True)
    for forbidden in ('"x"', '"y"', '"z"', "Cup|", "CoffeeMachine|", "objectId"):
        assert forbidden not in serialized


def test_private_registry_digest_binds_start_pose_and_public_contract() -> None:
    module = _module()
    poses = [
        {"x": float(index), "y": 0.9, "z": 0.0, "rotation": 0.0,
         "horizon": 0.0, "standing": True}
        for index in range(2)
    ]
    public_rows = [{
        "configuration_id": f"Fixture{index}",
        "scene": f"FloorPlan{index + 1}",
        "start_pose_digest": stable_digest(pose),
        "source_qualification_digest": str(index) * 64,
        "subgoal_route_id": f"Fixture{index}_subgoal",
        "fallback_route_id": f"Fixture{index}_fallback",
    } for index, pose in enumerate(poses)]
    private_rows = [{
        "configuration_id": f"Fixture{index}",
        "target_cup_object_id": f"Cup|{index}",
        "coffee_machine_object_id": f"CoffeeMachine|{index}",
        "start_action": {"action": "TeleportFull", **pose},
        "candidate_order": 1,
    } for index, pose in enumerate(poses)]
    registry = module.build_private_registry(  # type: ignore[attr-defined]
        runtime_set_version="phase5-r2-frozen-runtime-set-v2",
        public_rows=public_rows,
        private_rows=private_rows,
        source_outputs=["outputs/private"],
    )
    digest = registry.pop("private_configuration_set_digest")
    assert stable_digest(registry) == digest
    assert registry["boundary"] == PRIVATE_BOUNDARY
    assert registry["planner_visible"] is False
    assert registry["included_in_planner_metrics"] is False
    assert registry["configuration_count"] == 2
    assert "Cup|0" in json.dumps(registry)


def test_v1_runtime_defaults_remain_unchanged() -> None:
    from embodied_memory_thor.phase5 import frozen_r2

    assert frozen_r2.R2_RUNTIME_SET_VERSION == "phase5-r2-frozen-runtime-set-v1"
    assert frozen_r2.DEFAULT_PUBLIC_SET_PATH.name == "phase5_r2_frozen_runtime_v1.json"


def test_shared_private_source_is_expanded_only_once() -> None:
    source = (ROOT / "scripts" / "freeze_phase5_r2_runtime_v2.py").read_text(
        encoding="utf-8"
    )
    assert "if relative in loaded_sources:" in source
    assert "continue" in source
    config = json.loads(FREEZE_CONFIG.read_text(encoding="utf-8"))
    sources = [row["private_source"] for row in config["configurations"]]
    assert len(sources) == 6
    assert len(set(sources)) == 5


def test_generated_v2_runtime_loads_all_six_and_public_evidence_is_safe() -> None:
    from embodied_memory_thor.phase5.frozen_r2_v2 import load_frozen_r2_runtime_v2

    evidence = json.loads(FREEZE_EVIDENCE.read_text(encoding="utf-8"))
    public_path = ROOT / evidence["public_runtime_registry"]
    routes_path = ROOT / evidence["public_route_registry"]
    assert hashlib.sha256(public_path.read_bytes()).hexdigest() == evidence[
        "public_runtime_registry_sha256"
    ]
    assert hashlib.sha256(routes_path.read_bytes()).hexdigest() == evidence[
        "public_route_registry_sha256"
    ]
    action_counts = {}
    for configuration_id in evidence["configuration_order"]:
        runtime = load_frozen_r2_runtime_v2(configuration_id)
        action_counts[configuration_id] = (
            runtime.subgoal_route.action_count,
            runtime.fallback_route.action_count,
        )
    assert action_counts == {
        "FloorPlan3_R2_fixed_start_001": (6, 110),
        "FloorPlan4_R2_fixed_start_001": (11, 110),
        "FloorPlan6_R2_fixed_start_001": (13, 403),
        "FloorPlan7_R2_fixed_start_001": (11, 685),
        "FloorPlan10_R2_fixed_start_001": (12, 512),
        "FloorPlan12_R2_fixed_start_001": (9, 1367),
    }
    serialized = public_path.read_text(encoding="utf-8") + routes_path.read_text(
        encoding="utf-8"
    ) + json.dumps(evidence)
    for forbidden in ('"x"', '"y"', '"z"', "Cup|", "CoffeeMachine|", "objectId", "TeleportFull"):
        assert forbidden not in serialized

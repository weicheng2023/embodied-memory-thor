#!/usr/bin/env python3
"""Freeze the conservative six-configuration R2 replacement runtime v3."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FREEZE_VERSION = "phase5-r2-runtime-freeze-v3"
RUNTIME_SET_VERSION = "phase5-r2-frozen-runtime-set-v3"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "phase5_r2_runtime_freeze_v3.json"


def _load_v2_module() -> Any:
    path = PROJECT_ROOT / "scripts" / "freeze_phase5_r2_runtime_v2.py"
    spec = importlib.util.spec_from_file_location("phase5_r2_runtime_freeze_v2_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the immutable runtime-v2 freeze implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_v2 = _load_v2_module()
_v2.FREEZE_VERSION = FREEZE_VERSION
_v2.RUNTIME_SET_VERSION = RUNTIME_SET_VERSION
_v2.DEFAULT_CONFIG = DEFAULT_CONFIG
_validate_base = _v2.validate_freeze_config


def validate_freeze_config(config: Mapping[str, Any]) -> None:
    """Require the immutable v2 inputs plus the passed replacement gate."""

    _validate_base(config)
    order = list(config.get("configuration_order", []))
    expected = [
        "FloorPlan3_R2_fixed_start_001",
        "FloorPlan4_R2_fixed_start_001",
        "FloorPlan6_R2_fixed_start_001",
        "FloorPlan7_R2_fixed_start_001",
        "FloorPlan12_R2_fixed_start_001",
        "FloorPlan17_R2_fixed_start_001",
    ]
    if order != expected:
        raise ValueError("runtime-v3 replacement order mismatch")
    if config.get("excluded_configuration_id") != "FloorPlan10_R2_fixed_start_001":
        raise ValueError("runtime-v3 excluded configuration mismatch")
    replacement = str(config.get("replacement_configuration_id", ""))
    if replacement != expected[-1]:
        raise ValueError("runtime-v3 replacement configuration mismatch")
    gate_path = PROJECT_ROOT / str(config.get("replacement_gate_evidence", ""))
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    required = {
        "configuration_id": replacement,
        "passed": True,
        "success": True,
        "information_boundary_passed": True,
        "production_equivalent_gate_passed": True,
        "replacement_freeze_allowed": True,
        "included_in_formal_aggregate": False,
    }
    for key, expected_value in required.items():
        if gate.get(key) != expected_value:
            raise ValueError(f"replacement gate evidence mismatch: {key}")
    zero_fields = (
        "invalid_action_count",
        "shared_route_action_recovery_action_count",
        "shared_route_action_recovery_attempt_count",
        "shared_route_action_recovery_terminal_failure_count",
        "shared_search_action_failure_count",
        "shared_subgoal_action_failure_count",
        "target_lock_interaction_recovery_action_count",
    )
    if any(int(gate.get(field, -1)) != 0 for field in zero_fields):
        raise ValueError("replacement gate contains a forbidden execution failure")


_v2.validate_freeze_config = validate_freeze_config
build_private_registry = _v2.build_private_registry
_public_material = _v2._public_material
freeze = _v2.freeze


def main(argv: list[str] | None = None) -> int:
    return _v2.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

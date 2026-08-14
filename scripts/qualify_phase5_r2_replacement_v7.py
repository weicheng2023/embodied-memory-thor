#!/usr/bin/env python3
"""Qualify one ordered R2 replacement scene after FloorPlan10 exclusion."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase5.budgeted_fallback import (  # noqa: E402
    BUDGETED_VISUAL_FALLBACK_ACTION_LIMIT,
    BUDGETED_VISUAL_FALLBACK_POLICY_VERSION,
)


QUALIFICATION_VERSION = "phase5-r2-replacement-native-qualification-v7"
SCRIPT_VERSION = "phase5-r2-replacement-budgeted-visual-v7"
REPLACEMENT_PROTOCOL_VERSION = "phase5-r2-floorplan10-replacement-v1"
BOUNDARY = "EVALUATOR-ONLY R2 REPLACEMENT V7 - NEVER PLANNER INPUT"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "phase5_r2_replacement_qualification_v7.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _v6_module() -> Any:
    path = PROJECT_ROOT / "scripts" / "qualify_phase5_r2_v6.py"
    spec = importlib.util.spec_from_file_location("phase5_r2_v6_frozen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load hash-frozen R2 v6 qualifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_config(config: Mapping[str, Any], scene: str) -> None:
    expected = {
        "qualification_version": QUALIFICATION_VERSION,
        "replacement_protocol_version": REPLACEMENT_PROTOCOL_VERSION,
        "inherited_qualification_version": "phase5-r2-native-qualification-v6",
        "adapter_version": "phase5-r2-budgeted-qualification-adapter-v1",
        "fallback_policy_version": BUDGETED_VISUAL_FALLBACK_POLICY_VERSION,
        "fallback_action_limit": BUDGETED_VISUAL_FALLBACK_ACTION_LIMIT,
        "candidate_pair_limit": 12,
        "candidate_freeze_before_task_outcomes": True,
        "qualification_runs_memory_variants": False,
        "images_saved": False,
        "gui_enabled": False,
        "formal_use_allowed": False,
        "floorplan17_or_later_allowed": True,
        "stop_after_first_qualified_replacement": True,
        "production_equivalent_gate_required": True,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"R2 replacement v7 config mismatch: {key}")
    scenes = config.get("authorized_scene_order")
    if not isinstance(scenes, list) or scene not in scenes:
        raise ValueError("scene is outside the pre-registered R2 replacement order")
    if scenes != [f"FloorPlan{index}" for index in range(17, 31)]:
        raise ValueError("R2 replacement scene order changed")
    if config.get("shared_variant_contract") != [
        "no_memory", "short_memory_k2", "object_memory"
    ]:
        raise ValueError("R2 replacement shared-variant contract mismatch")
    for relative, expected_hash in config.get("historical_artifacts_frozen", {}).items():
        path = (PROJECT_ROOT / str(relative)).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise ValueError("R2 replacement frozen source outside project") from exc
        if not path.is_file() or _sha256(path) != str(expected_hash):
            raise ValueError(f"historical artifact changed: {relative}")


def _patched_qualifier(config: Mapping[str, Any]) -> Any:
    v6 = _v6_module()
    v6.QUALIFICATION_VERSION = QUALIFICATION_VERSION
    v6.SCRIPT_VERSION = SCRIPT_VERSION
    v6.BOUNDARY = BOUNDARY
    module = v6._patch_v5(v6._v5_module(), config)
    original_summary = module.build_public_summary

    def build_public_summary(**kwargs: Any) -> dict[str, Any]:
        summary = original_summary(**kwargs)
        summary.update({
            "replacement_protocol_version": REPLACEMENT_PROTOCOL_VERSION,
            "excluded_configuration_id": config["excluded_configuration_id"],
            "replacement_selection_rule": config["replacement_selection_rule"],
            "production_equivalent_gate_required": True,
            "production_equivalent_gate_passed": False,
            "replacement_freeze_allowed": False,
        })
        return summary

    module.build_public_summary = build_public_summary
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    _validate_config(config, args.scene)
    module = _patched_qualifier(config)
    return int(module.main([
        "--scene", args.scene,
        "--output-dir", str(args.output_dir),
    ]))


if __name__ == "__main__":
    raise SystemExit(main())

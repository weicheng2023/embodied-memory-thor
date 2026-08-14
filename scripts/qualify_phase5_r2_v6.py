#!/usr/bin/env python3
"""Qualify one R2 scene using the budgeted visual fallback successor."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase5.budgeted_fallback import (  # noqa: E402
    BUDGETED_VISUAL_FALLBACK_ACTION_LIMIT,
    BUDGETED_VISUAL_FALLBACK_POLICY_VERSION,
    build_target_independent_budgeted_visual_fallback_route,
)


QUALIFICATION_VERSION = "phase5-r2-native-qualification-v6"
ADAPTER_VERSION = "phase5-r2-budgeted-qualification-adapter-v1"
SCRIPT_VERSION = "phase5-r2-qualification-budgeted-visual-v6"
BOUNDARY = "EVALUATOR-ONLY R2 V6 QUALIFICATION - NEVER PLANNER INPUT"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "phase5_r2_qualification_v6.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_config(config: Mapping[str, Any], scene: str) -> None:
    expected = {
        "qualification_version": QUALIFICATION_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "inherited_qualification_version": "phase5-r2-native-qualification-v5",
        "fallback_policy_version": BUDGETED_VISUAL_FALLBACK_POLICY_VERSION,
        "fallback_action_limit": BUDGETED_VISUAL_FALLBACK_ACTION_LIMIT,
        "candidate_pair_limit": 12,
        "candidate_freeze_before_task_outcomes": True,
        "qualification_runs_memory_variants": False,
        "images_saved": False,
        "gui_enabled": False,
        "formal_use_allowed": False,
        "floorplan17_or_later_allowed": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"R2 v6 config mismatch: {key}")
    scenes = config.get("authorized_scene_order")
    if not isinstance(scenes, list) or scene not in scenes:
        raise ValueError("scene is outside the pre-registered R2 v6 order")
    if config.get("shared_variant_contract") != [
        "no_memory", "short_memory_k2", "object_memory"
    ]:
        raise ValueError("R2 v6 shared-variant contract mismatch")
    for relative, expected_hash in config.get("historical_artifacts_frozen", {}).items():
        if _sha256(PROJECT_ROOT / str(relative)) != str(expected_hash):
            raise ValueError(f"historical artifact changed: {relative}")


def _v5_module() -> Any:
    path = PROJECT_ROOT / "scripts" / "qualify_phase5_r2_v5.py"
    spec = importlib.util.spec_from_file_location("phase5_r2_v5_frozen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load hash-frozen R2 v5 qualifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _coordinate_free_route_metrics(
    candidate_plan: Mapping[str, Any],
    selected_private: Mapping[str, Any] | None,
) -> dict[str, Any]:
    routes: list[Mapping[str, Any]] = []
    if selected_private is not None:
        selected_route = selected_private.get("fallback_route_private")
        if isinstance(selected_route, Mapping):
            routes = [selected_route]
    if not routes:
        raw_pairs = candidate_plan.get("candidate_pairs", [])
        if isinstance(raw_pairs, Sequence):
            for row in raw_pairs:
                if not isinstance(row, Mapping):
                    continue
                route = row.get("fallback_route")
                if isinstance(route, Mapping):
                    routes.append(route)
    counts = sorted(
        int(route["action_count"])
        for route in routes if isinstance(route.get("action_count"), int)
    )
    viewpoints = sorted(
        int(route["viewpoint_count"])
        for route in routes if isinstance(route.get("viewpoint_count"), int)
    )
    coverage = routes[0].get("coverage_summary") if routes else None
    return {
        "fallback_action_count_min": counts[0] if counts else None,
        "fallback_action_count_max": counts[-1] if counts else None,
        "fallback_viewpoint_count_min": viewpoints[0] if viewpoints else None,
        "fallback_viewpoint_count_max": viewpoints[-1] if viewpoints else None,
        "fallback_coverage_summary": dict(coverage) if isinstance(coverage, Mapping) else None,
    }


def _patch_v5(module: Any, config: Mapping[str, Any]) -> Any:
    module.QUALIFICATION_VERSION = QUALIFICATION_VERSION
    module.SCRIPT_VERSION = SCRIPT_VERSION
    module.BOUNDARY = BOUNDARY
    module.VISUAL_FALLBACK_POLICY_VERSION = BUDGETED_VISUAL_FALLBACK_POLICY_VERSION
    module.VISUAL_FALLBACK_ACTION_LIMIT = BUDGETED_VISUAL_FALLBACK_ACTION_LIMIT
    module.build_target_independent_visual_fallback_route = (
        build_target_independent_budgeted_visual_fallback_route
    )

    original_classifier = module.classify_candidate_batch

    def classify_candidate_batch(rows: Sequence[Mapping[str, Any]]) -> str:
        classification = original_classifier(rows)
        return {
            "visual_fallback_route_construction_ineligible": (
                "budgeted_visual_fallback_construction_ineligible"
            ),
            "visual_fallback_route_execution_ineligible": (
                "budgeted_visual_fallback_execution_ineligible"
            ),
            "target_reacquisition_not_achieved_by_registered_visual_fallback": (
                "budgeted_visual_fallback_reacquisition_not_achieved"
            ),
        }.get(classification, classification)

    module.classify_candidate_batch = classify_candidate_batch
    original_public_route = module._public_route

    def public_route(legacy: Any, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("role") == "target_independent_fallback":
            kwargs["route_id"] = str(kwargs["route_id"]).replace(
                "fallback_visual_v1", "fallback_budgeted_visual_v1"
            )
        return original_public_route(legacy, **kwargs)

    module._public_route = public_route
    original_summary = module.build_public_summary
    skip_classes = set(config["scene_skip_classifications"])

    def build_public_summary(**kwargs: Any) -> dict[str, Any]:
        summary = original_summary(**kwargs)
        classification = str(kwargs.get("classification", ""))
        if summary.get("passed") is not True:
            summary["scene_skip_allowed"] = classification in skip_classes
        summary.update({
            "adapter_version": ADAPTER_VERSION,
            "fallback_viewpoint_selection_policy": config[
                "fallback_viewpoint_selection_policy"
            ],
            "fallback_grid_bin_size_steps": config["fallback_grid_bin_size_steps"],
            "fallback_candidate_outcome_input_used": False,
            "fallback_memory_input_used": False,
            "shared_variant_contract": list(config["shared_variant_contract"]),
            "fallback_line_of_sight_coverage_claimed": False,
            **_coordinate_free_route_metrics(
                kwargs["candidate_plan"], kwargs.get("selected_private")
            ),
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
    module = _patch_v5(_v5_module(), config)
    return int(module.main([
        "--scene", args.scene,
        "--output-dir", str(args.output_dir),
    ]))


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the excluded 6 x 3 R2 runtime-v3 integration dry run."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase4.runner import (  # noqa: E402
    ThorEpisodeConfig,
    ThorEpisodeRunner,
)
from embodied_memory_thor.phase5.frozen_r2_v3 import (  # noqa: E402
    R2_RUNTIME_SET_VERSION_V3,
    load_frozen_r2_runtime_v3,
)
from embodied_memory_thor.phase5.protocol import PHASE5_VARIANTS  # noqa: E402


DRY_RUN_VERSION = "phase5-r2-runtime-v3-six-configuration-dry-run-v1"
DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs"
    / "phase5_r2_runtime_v3_six_configuration_dry_run_v1.json"
)
EXPECTED_CONFIGURATION_ORDER = (
    "FloorPlan3_R2_fixed_start_001",
    "FloorPlan4_R2_fixed_start_001",
    "FloorPlan6_R2_fixed_start_001",
    "FloorPlan7_R2_fixed_start_001",
    "FloorPlan12_R2_fixed_start_001",
    "FloorPlan17_R2_fixed_start_001",
)


def _integration_module() -> Any:
    path = PROJECT_ROOT / "scripts" / "run_phase5_r2_runtime_v3_integration_probe_v1.py"
    spec = importlib.util.spec_from_file_location("phase5_r2_runtime_v3_probe_frozen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the frozen runtime-v3 integration audit")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_state() -> tuple[str, str, bool]:
    def value(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=PROJECT_ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip()

    return (
        value("rev-parse", "HEAD"),
        value("rev-parse", "@{upstream}"),
        bool(value("status", "--porcelain")),
    )


def validate_dry_run_config(config: Mapping[str, Any]) -> None:
    expected = {
        "dry_run_version": DRY_RUN_VERSION,
        "runtime_set_version": R2_RUNTIME_SET_VERSION_V3,
        "task": "thor_cup_after_coffee_subgoal",
        "panel": "r2_stable",
        "condition": "stable",
        "configuration_order": list(EXPECTED_CONFIGURATION_ORDER),
        "variants": list(PHASE5_VARIANTS),
        "expected_cell_count": 18,
        "max_steps_per_episode": 2048,
        "mode": "formal",
        "included_in_formal_aggregate": False,
        "save_frames": False,
        "trace_html": False,
        "visualize": False,
        "save_evaluator_debug": False,
        "formal_execution_authorized": False,
        "episode_reuse_allowed": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"runtime-v3 dry-run mismatch: {key}")
    frozen = config.get("historical_artifacts_frozen", {})
    if not isinstance(frozen, Mapping) or not frozen:
        raise ValueError("runtime-v3 dry-run frozen sources missing")
    for relative, digest in frozen.items():
        path = (PROJECT_ROOT / str(relative)).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise ValueError("runtime-v3 dry-run source outside project") from exc
        if not path.is_file() or _sha256(path) != str(digest):
            raise ValueError(f"runtime-v3 dry-run source changed: {relative}")
    public_set = json.loads(
        (PROJECT_ROOT / "configs" / "phase5_r2_frozen_runtime_v3.json")
        .read_text(encoding="utf-8")
    )
    public_order = [
        row.get("configuration_id") for row in public_set.get("configurations", [])
        if isinstance(row, Mapping)
    ]
    if public_order != list(EXPECTED_CONFIGURATION_ORDER):
        raise ValueError("runtime-v3 dry-run public runtime order mismatch")
    integration = _integration_module()
    serialized = json.dumps(config, ensure_ascii=False, sort_keys=True)
    if any(token in serialized for token in integration.FORBIDDEN_PUBLIC_TOKENS):
        raise ValueError("runtime-v3 dry-run config contains private material")


def run_dry_run(*, config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_dry_run_config(config)
    head, upstream, dirty = _git_state()
    if dirty or head != upstream:
        raise ValueError("runtime-v3 dry-run requires a clean pushed HEAD")
    if output_dir.exists():
        raise ValueError("runtime-v3 dry-run output already exists")
    integration = _integration_module()
    gate = integration._gate_module()
    output_dir.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    stop_reason = ""
    for configuration_id in EXPECTED_CONFIGURATION_ORDER:
        runtime = load_frozen_r2_runtime_v3(configuration_id)
        for variant in PHASE5_VARIANTS:
            cell_id = f"{configuration_id}__{variant}"
            episode_dir = output_dir / cell_id
            summary = ThorEpisodeRunner(
                ThorEpisodeConfig(
                    task=str(config["task"]),
                    scene=runtime.configuration.scene,
                    planner="deterministic", memory=variant,
                    search_route_id=runtime.fallback_route.route_id,
                    subgoal_route_id=runtime.subgoal_route.route_id,
                    condition="stable", mode="formal",
                    max_steps=int(config["max_steps_per_episode"]),
                    output_dir=episode_dir, save_frames=False, trace_html=False,
                    visualize=False, save_evaluator_debug=False,
                    included_in_formal_aggregate=False,
                    run_purpose="phase5_r2_runtime_v3_six_configuration_dry_run_v1",
                ),
                search_route=runtime.fallback_route,
                subgoal_route=runtime.subgoal_route,
                evaluator_setup=runtime.configuration,
            ).run()
            errors, metrics = integration.audit_variant(
                variant=variant, summary=summary, episode_dir=episode_dir,
                runtime=runtime, gate=gate, expected_revision=head,
            )
            row = {
                "cell_index": len(rows) + 1,
                "configuration_id": configuration_id,
                "scene": runtime.configuration.scene,
                "variant": variant,
                "success": summary.get("success"),
                "steps": summary.get("steps"),
                "information_boundary_passed": summary.get(
                    "information_boundary_passed"
                ),
                **metrics,
                "audit_errors": errors,
            }
            rows.append(row)
            if errors:
                stop_reason = f"cell_{len(rows)}_integrity_failure"
                break
        if stop_reason:
            break
    passed = len(rows) == int(config["expected_cell_count"]) and all(
        not row["audit_errors"] for row in rows
    )
    result = {
        "dry_run_version": DRY_RUN_VERSION,
        "runtime_set_version": R2_RUNTIME_SET_VERSION_V3,
        "code_revision": head,
        "working_tree_dirty": False,
        "included_in_formal_aggregate": False,
        "expected_cell_count": int(config["expected_cell_count"]),
        "completed_cell_count": len(rows),
        "stopped_early": len(rows) < int(config["expected_cell_count"]),
        "stop_reason": stop_reason,
        "passed": passed,
        "rows": rows,
        "claim_boundary": config["claim_boundary"],
        "next_gate": (
            "freeze the excluded dry-run evidence and design fresh formal-v5 readiness"
            if passed else "stop formal progression and classify the first dry-run failure"
        ),
    }
    public = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if any(token in public for token in integration.FORBIDDEN_PUBLIC_TOKENS):
        raise ValueError("runtime-v3 dry-run public result contains private material")
    integration._write_json(output_dir / "dry_run_summary.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_dry_run(
            config_path=args.config.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
        )
    except (
        json.JSONDecodeError, OSError, RuntimeError, subprocess.SubprocessError,
        TypeError, ValueError,
    ) as exc:
        print(f"phase5_r2_runtime_v3_dry_run_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

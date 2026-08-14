#!/usr/bin/env python3
"""Run one excluded FloorPlan17 triplet through frozen R2 runtime-v3."""

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
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


PROBE_VERSION = "phase5-r2-runtime-v3-integration-probe-v1"
CONFIGURATION_ID = "FloorPlan17_R2_fixed_start_001"
DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "phase5_r2_runtime_v3_integration_probe_v1.json"
)
FORBIDDEN_PUBLIC_TOKENS = (
    '"x"', '"y"', '"z"', '"objectId"', '"target_point"',
    '"anchor_id"', '"support_id"', '"reachable_positions"',
    "Cup|", "CoffeeMachine|", "TeleportFull", "PlaceObjectAtPoint",
)
FORBIDDEN_ORDINARY_KEYS = {
    "anchor_id", "candidate_order", "coffee_machine_object_id",
    "destination_pose", "private_registry", "reachable_positions",
    "start_action", "support_id", "target_cup_object_id", "target_point",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _walk_forbidden(value: Any, path: str = "") -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            child = f"{path}.{key}" if path else key
            if key.casefold() in FORBIDDEN_ORDINARY_KEYS:
                violations.append(child)
            violations.extend(_walk_forbidden(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_walk_forbidden(item, f"{path}[{index}]"))
    return violations


def _gate_module() -> Any:
    path = PROJECT_ROOT / "scripts" / "run_phase5_r2_floorplan17_production_gate_v1.py"
    spec = importlib.util.spec_from_file_location("phase5_floorplan17_gate_frozen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the frozen FloorPlan17 production gate audit")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def validate_probe_config(config: Mapping[str, Any]) -> None:
    expected = {
        "probe_version": PROBE_VERSION,
        "runtime_set_version": R2_RUNTIME_SET_VERSION_V3,
        "configuration_id": CONFIGURATION_ID,
        "scene": "FloorPlan17",
        "task": "thor_cup_after_coffee_subgoal",
        "panel": "r2_stable",
        "condition": "stable",
        "variants": list(PHASE5_VARIANTS),
        "max_steps": 2048,
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
            raise ValueError(f"runtime-v3 integration probe mismatch: {key}")
    frozen = config.get("historical_artifacts_frozen", {})
    if not isinstance(frozen, Mapping) or not frozen:
        raise ValueError("runtime-v3 integration probe frozen sources missing")
    for relative, digest in frozen.items():
        path = (PROJECT_ROOT / str(relative)).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise ValueError("runtime-v3 integration source outside project") from exc
        if not path.is_file() or _sha256(path) != str(digest):
            raise ValueError(f"runtime-v3 integration source changed: {relative}")
    public = json.dumps(config, ensure_ascii=False, sort_keys=True)
    if any(token in public for token in FORBIDDEN_PUBLIC_TOKENS):
        raise ValueError("runtime-v3 integration config contains private material")


def _ordinary_privacy_errors(episode_dir: Path) -> list[str]:
    errors: list[str] = []
    records: list[Any] = []
    for name in ("setup.jsonl", "episode.jsonl"):
        path = episode_dir / name
        if not path.is_file():
            errors.append(f"missing_ordinary_log:{name}")
            continue
        records.extend(
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        )
    errors.extend(f"ordinary_forbidden_key:{path}" for path in _walk_forbidden(records))
    ordinary = json.dumps(records, ensure_ascii=False, sort_keys=True)
    for token in ("TeleportFull", "PlaceObjectAtPoint"):
        if token in ordinary:
            errors.append(f"ordinary_native_action_leak:{token}")
    if not (episode_dir / "evaluator_setup.jsonl").is_file():
        errors.append("missing_private_setup_log")
    return errors


def audit_variant(
    *, variant: str, summary: Mapping[str, Any], episode_dir: Path,
    runtime: Any, gate: Any, expected_revision: str,
) -> tuple[list[str], dict[str, Any]]:
    errors, metrics = gate._audit_episode(
        summary=summary, episode_dir=episode_dir, runtime=runtime
    )
    errors.extend(_ordinary_privacy_errors(episode_dir))
    if summary.get("memory") != variant:
        errors.append("summary:memory")
    if summary.get("evidence_status") != "excluded_engineering_probe":
        errors.append("summary:evidence_status")
    if summary.get("intervention_count") != 0:
        errors.append("summary:intervention_count")
    manifest_path = episode_dir / "run_manifest.json"
    if not manifest_path.is_file():
        errors.append("missing_run_manifest")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("code_revision") != expected_revision:
            errors.append("manifest:code_revision")
        if manifest.get("working_tree_dirty") is not False:
            errors.append("manifest:working_tree_dirty")
        if manifest.get("included_in_formal_aggregate") is not False:
            errors.append("manifest:included_in_formal_aggregate")
        if manifest.get("evidence_status") != "excluded_engineering_probe":
            errors.append("manifest:evidence_status")
    if variant == "no_memory" and int(summary.get("memory_retrieval_count", -1)) != 0:
        errors.append("no_memory:memory_retrieval_count")
    if variant == "short_memory_k2" and (
        summary.get("short_memory_evicted_before_reacquisition") is not True
    ):
        errors.append("short_memory_k2:eviction_not_observed")
    if variant == "object_memory":
        if int(summary.get("memory_retrieval_count", 0)) < 1:
            errors.append("object_memory:retrieval_not_exercised")
        if int(summary.get("memory_guided_action_count", 0)) < 1:
            errors.append("object_memory:guidance_not_exercised")
    metrics.update({
        "target_reacquisition_action_count": summary.get(
            "target_reacquisition_action_count"
        ),
        "memory_retrieval_count": summary.get("memory_retrieval_count"),
        "memory_guided_action_count": summary.get("memory_guided_action_count"),
        "short_memory_evicted_before_reacquisition": summary.get(
            "short_memory_evicted_before_reacquisition"
        ),
        "shared_search_entry_recovery_action_count": summary.get(
            "shared_search_entry_recovery_action_count"
        ),
    })
    return errors, metrics


def run_probe(*, config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_probe_config(config)
    head, upstream, dirty = _git_state()
    if dirty or head != upstream:
        raise ValueError("runtime-v3 integration probe requires a clean pushed HEAD")
    if output_dir.exists():
        raise ValueError("runtime-v3 integration probe output already exists")
    runtime = load_frozen_r2_runtime_v3(CONFIGURATION_ID)
    public = runtime.configuration.public_reference()
    bindings = {
        "scene": public["scene"],
        "private_configuration_set_digest": public["private_configuration_set_digest"],
        "source_qualification_digest": public["source_qualification_digest"],
        "subgoal_route_id": public["subgoal_route_id"],
        "fallback_route_id": public["fallback_route_id"],
        "subgoal_route_action_sequence_digest": runtime.subgoal_route.action_sequence_digest,
        "fallback_route_action_sequence_digest": runtime.fallback_route.action_sequence_digest,
    }
    for key, value in bindings.items():
        if str(config.get(key, "")) != str(value):
            raise ValueError(f"runtime-v3 integration frozen binding mismatch: {key}")

    gate = _gate_module()
    output_dir.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    for variant in PHASE5_VARIANTS:
        episode_dir = output_dir / variant
        summary = ThorEpisodeRunner(
            ThorEpisodeConfig(
                task=str(config["task"]), scene=str(config["scene"]),
                planner="deterministic", memory=variant,
                search_route_id=runtime.fallback_route.route_id,
                subgoal_route_id=runtime.subgoal_route.route_id,
                condition="stable", mode="formal", max_steps=int(config["max_steps"]),
                output_dir=episode_dir, save_frames=False, trace_html=False,
                visualize=False, save_evaluator_debug=False,
                included_in_formal_aggregate=False,
                run_purpose="phase5_r2_runtime_v3_integration_probe_v1",
            ),
            search_route=runtime.fallback_route,
            subgoal_route=runtime.subgoal_route,
            evaluator_setup=runtime.configuration,
        ).run()
        errors, metrics = audit_variant(
            variant=variant, summary=summary, episode_dir=episode_dir,
            runtime=runtime, gate=gate, expected_revision=head,
        )
        rows.append({
            "variant": variant,
            "success": summary.get("success"),
            "steps": summary.get("steps"),
            "information_boundary_passed": summary.get(
                "information_boundary_passed"
            ),
            **metrics,
            "audit_errors": errors,
        })
        if errors:
            break
    passed = len(rows) == len(PHASE5_VARIANTS) and all(
        not row["audit_errors"] for row in rows
    )
    result = {
        "probe_version": PROBE_VERSION,
        "runtime_set_version": R2_RUNTIME_SET_VERSION_V3,
        "code_revision": head,
        "working_tree_dirty": False,
        "configuration_id": CONFIGURATION_ID,
        "included_in_formal_aggregate": False,
        "completed_variant_count": len(rows),
        "stopped_early": len(rows) < len(PHASE5_VARIANTS),
        "passed": passed,
        "rows": rows,
        "claim_boundary": config["claim_boundary"],
        "next_gate": (
            "freeze this excluded triplet and pre-register a six-configuration runtime-v3 dry run"
            if passed else "stop formal progression and classify the first integration failure"
        ),
    }
    public_text = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if any(token in public_text for token in FORBIDDEN_PUBLIC_TOKENS):
        raise ValueError("runtime-v3 integration result contains private material")
    _write_json(output_dir / "probe_summary.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_probe(
            config_path=args.config.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
        )
    except (
        json.JSONDecodeError, OSError, RuntimeError, subprocess.SubprocessError,
        TypeError, ValueError,
    ) as exc:
        print(f"phase5_r2_runtime_v3_integration_probe_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

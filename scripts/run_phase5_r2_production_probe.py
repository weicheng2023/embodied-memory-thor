#!/usr/bin/env python3
"""Run the precommitted excluded R2 production integration triplet."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase4.runner import ThorEpisodeConfig, ThorEpisodeRunner  # noqa: E402
from embodied_memory_thor.phase5.frozen_r2 import load_frozen_r2_runtime  # noqa: E402
from embodied_memory_thor.phase5.protocol import PHASE5_REQUIRED_METRICS, PHASE5_VARIANTS  # noqa: E402
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "phase5_r2_production_integration_probe_v1.json"
FORBIDDEN_ORDINARY_KEYS = {
    "anchor_id",
    "candidate_order",
    "coffee_machine_object_id",
    "destination_pose",
    "private_registry",
    "reachable_positions",
    "start_action",
    "target_cup_object_id",
    "target_point",
}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git_state() -> tuple[str, bool]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    return revision, dirty


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


def validate_probe_config(config: Mapping[str, Any]) -> None:
    if config.get("probe_version") != "phase5-r2-production-integration-probe-v1":
        raise ValueError("probe_version mismatch")
    if (
        config.get("task") != "thor_cup_after_coffee_subgoal"
        or config.get("panel") != "r2_stable"
        or config.get("condition") != "stable"
    ):
        raise ValueError("probe task/panel/condition mismatch")
    if tuple(config.get("variants", ())) != PHASE5_VARIANTS:
        raise ValueError("probe variants/order mismatch")
    if not isinstance(config.get("max_steps"), int) or int(config["max_steps"]) < 1:
        raise ValueError("probe max_steps must be positive")
    for key in (
        "save_frames", "trace_html", "visualize", "save_evaluator_debug",
        "included_in_formal_aggregate",
    ):
        if config.get(key) is not False:
            raise ValueError(f"probe output/evidence policy mismatch: {key}")
    if config.get("expected_episode_evidence_status") != "excluded_engineering_probe":
        raise ValueError("probe expected evidence status mismatch")
    if config.get("run_purpose") != "phase5_r2_production_integration_probe":
        raise ValueError("probe run purpose mismatch")


def _audit_episode(
    *, summary: Mapping[str, Any], episode_dir: Path,
    subgoal_digest: str, fallback_digest: str,
) -> list[str]:
    errors: list[str] = []
    for key in PHASE5_REQUIRED_METRICS:
        if key not in summary:
            errors.append(f"missing_metric:{key}")
    if summary.get("success") is not True:
        errors.append(f"episode_failed:{summary.get('failure_reason', '')}")
    if summary.get("information_boundary_passed") is not True:
        errors.append("information_boundary_failed")
    if summary.get("shared_subgoal_action_sequence_digest") != subgoal_digest:
        errors.append("subgoal_route_digest")
    if summary.get("shared_search_action_sequence_digest") != fallback_digest:
        errors.append("fallback_route_digest")
    if summary.get("included_in_formal_aggregate") is not False:
        errors.append("summary_formal_aggregate_label")
    if summary.get("evidence_status") != "excluded_engineering_probe":
        errors.append("summary_evidence_status")
    if summary.get("intervention_count") != 0:
        errors.append("unexpected_intervention")

    manifest = json.loads((episode_dir / "run_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("included_in_formal_aggregate") is not False:
        errors.append("manifest_formal_aggregate_label")
    if manifest.get("evidence_status") != "excluded_engineering_probe":
        errors.append("manifest_evidence_status")

    records: list[Any] = []
    for name in ("setup.jsonl", "episode.jsonl"):
        for line in (episode_dir / name).read_text(encoding="utf-8").splitlines():
            records.append(json.loads(line))
    errors.extend(
        f"ordinary_forbidden_key:{path}" for path in _walk_forbidden(records)
    )
    ordinary = json.dumps(records, ensure_ascii=False, sort_keys=True)
    if "TeleportFull" in ordinary:
        errors.append("ordinary_native_action_leak:TeleportFull")
    if not (episode_dir / "evaluator_setup.jsonl").is_file():
        errors.append("missing_private_setup_log")
    return errors


def run_probe(*, config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_probe_config(config)
    revision, dirty = _git_state()
    if dirty:
        raise ValueError("R2 production probe requires a clean worktree")
    if output_dir.exists():
        raise ValueError("probe output directory already exists")
    runtime = load_frozen_r2_runtime(str(config["configuration_id"]))
    public = runtime.configuration.public_reference()
    for key in (
        "scene", "private_configuration_set_digest", "source_qualification_digest",
        "subgoal_route_id", "fallback_route_id",
    ):
        if str(config.get(key, "")) != str(public.get(key, "")):
            raise ValueError(f"probe frozen configuration mismatch: {key}")
    if config.get("subgoal_route_action_sequence_digest") != runtime.subgoal_route.action_sequence_digest:
        raise ValueError("probe subgoal-route digest mismatch")
    if config.get("fallback_route_action_sequence_digest") != runtime.fallback_route.action_sequence_digest:
        raise ValueError("probe fallback-route digest mismatch")

    output_dir.mkdir(parents=True)
    _write_json(output_dir / "probe_manifest.json", {
        **config, "code_revision": revision, "working_tree_dirty": False,
        "private_coordinates_in_launch_manifest": False, "output_dir": str(output_dir),
    })
    rows: list[dict[str, Any]] = []
    stopped_early = False
    for variant in PHASE5_VARIANTS:
        episode_dir = output_dir / variant
        episode = ThorEpisodeRunner(
            ThorEpisodeConfig(
                task=str(config["task"]), scene=str(config["scene"]),
                planner="deterministic", memory=variant,
                subgoal_route_id=runtime.subgoal_route.route_id,
                search_route_id=runtime.fallback_route.route_id,
                condition="stable", mode="formal", max_steps=int(config["max_steps"]),
                output_dir=episode_dir, save_frames=False, trace_html=False,
                visualize=False, save_evaluator_debug=False,
                included_in_formal_aggregate=False,
                run_purpose=str(config["run_purpose"]),
            ),
            subgoal_route=runtime.subgoal_route,
            search_route=runtime.fallback_route,
            evaluator_setup=runtime.configuration,
        ).run()
        errors = _audit_episode(
            summary=episode, episode_dir=episode_dir,
            subgoal_digest=runtime.subgoal_route.action_sequence_digest,
            fallback_digest=runtime.fallback_route.action_sequence_digest,
        )
        rows.append({
            "variant": variant,
            "success": episode.get("success"),
            "steps": episode.get("steps"),
            "target_reacquisition_action_count": episode.get("target_reacquisition_action_count"),
            "memory_guided_action_count": episode.get("memory_guided_action_count"),
            "shared_subgoal_coverage_action_count": episode.get("shared_subgoal_coverage_action_count"),
            "shared_search_coverage_action_count": episode.get("shared_search_coverage_action_count"),
            "short_memory_evicted_before_reacquisition": episode.get("short_memory_evicted_before_reacquisition"),
            "information_boundary_passed": episode.get("information_boundary_passed"),
            "audit_errors": errors,
        })
        if errors:
            stopped_early = variant != PHASE5_VARIANTS[-1]
            break
    passed = len(rows) == len(PHASE5_VARIANTS) and all(not row["audit_errors"] for row in rows)
    result = {
        "probe_version": config["probe_version"],
        "code_revision": revision,
        "working_tree_dirty": False,
        "configuration_id": config["configuration_id"],
        "included_in_formal_aggregate": False,
        "passed": passed,
        "stopped_early": stopped_early,
        "completed_variant_count": len(rows),
        "rows": rows,
        "claim_boundary": config["claim_boundary"],
        "next_gate": (
            "continue ascending R2 scene qualification until six configurations"
            if passed else "stop and diagnose the first R2 production integration failure"
        ),
    }
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
    except (json.JSONDecodeError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"phase5_r2_probe_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

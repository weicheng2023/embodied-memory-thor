#!/usr/bin/env python3
"""Run one excluded production-equivalent FloorPlan17 no-memory gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
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
from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.phase5.frozen_r2 import (  # noqa: E402
    FrozenR2Configuration,
    FrozenR2Runtime,
)
from embodied_memory_thor.phase5.search import FrozenSearchRoute  # noqa: E402
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "phase5_r2_floorplan17_production_gate_v1.json"
)
PUBLIC_CANDIDATE = (
    PROJECT_ROOT / "configs" / "phase5_r2_floorplan17_replacement_candidate_v1.json"
)
PRIVATE_CANDIDATE = (
    PROJECT_ROOT
    / "outputs"
    / "phase5_r2_replacement_v7_floorplan17_38af4c6"
    / "evaluator_only_configuration_registry_draft.json"
)
GATE_VERSION = "phase5-r2-floorplan17-production-equivalent-gate-v1"
CONFIGURATION_ID = "FloorPlan17_R2_fixed_start_001"
PRIVATE_BOUNDARY = "EVALUATOR-ONLY R2 REPLACEMENT V7 - NEVER PLANNER INPUT"
FORBIDDEN_PUBLIC_TOKENS = (
    '"objectId"',
    '"target_point"',
    '"anchor_id"',
    '"support_id"',
    '"reachable_positions"',
    "TeleportFull",
    "PlaceObjectAtPoint",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


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


def _route(raw: Mapping[str, Any]) -> FrozenSearchRoute:
    route = FrozenSearchRoute(
        route_id=str(raw.get("route_id", "")),
        task=str(raw.get("task", "")),
        scene=str(raw.get("scene", "")),
        source_qualification_route_digest=str(
            raw.get("source_qualification_route_digest", "")
        ),
        action_sequence_digest=str(raw.get("action_sequence_digest", "")),
        action_codes=str(raw.get("action_codes", "")),
        route_role=str(raw.get("route_role", "")),
        qualification_goal_input_used=raw.get(
            "qualification_goal_input_used", False
        ),
        target_or_anchor_input_used=raw.get(
            "target_or_anchor_input_used", False
        ),
        schema_version=str(raw.get("schema_version", "")),
        entry_position_tolerance_meters=float(
            raw.get("entry_position_tolerance_meters", 0.05)
        ),
        entry_angle_tolerance_degrees=float(
            raw.get("entry_angle_tolerance_degrees", 1.0)
        ),
    )
    route.validate()
    if route.action_count != int(raw.get("action_count", -1)):
        raise ValueError("FloorPlan17 public route action count mismatch")
    return route


def load_candidate_runtime() -> FrozenR2Runtime:
    public = json.loads(PUBLIC_CANDIDATE.read_text(encoding="utf-8"))
    private = json.loads(PRIVATE_CANDIDATE.read_text(encoding="utf-8"))
    if public.get("configuration_id") != CONFIGURATION_ID:
        raise ValueError("FloorPlan17 public candidate ID mismatch")
    if (
        private.get("configuration_id") != CONFIGURATION_ID
        or private.get("boundary") != PRIVATE_BOUNDARY
    ):
        raise ValueError("FloorPlan17 private candidate boundary mismatch")
    for key in ("scene", "start_pose_digest", "source_qualification_digest"):
        if str(public.get(key, "")) != str(private.get(key, "")):
            raise ValueError(f"FloorPlan17 public/private mismatch: {key}")
    start_action = private.get("start_action", {})
    if not isinstance(start_action, Mapping) or start_action.get("action") != "TeleportFull":
        raise ValueError("FloorPlan17 private start action is invalid")
    pose = dict(start_action)
    pose.pop("action", None)
    if stable_digest(pose) != str(public.get("start_pose_digest", "")):
        raise ValueError("FloorPlan17 private start pose digest mismatch")
    subgoal_raw = public.get("subgoal_route", {})
    fallback_raw = public.get("fallback_route", {})
    if not isinstance(subgoal_raw, Mapping) or not isinstance(fallback_raw, Mapping):
        raise ValueError("FloorPlan17 public routes are missing")
    subgoal_route = _route(subgoal_raw)
    fallback_route = _route(fallback_raw)
    source_digest = str(public.get("source_qualification_digest", ""))
    if (
        subgoal_route.source_qualification_route_digest != source_digest
        or fallback_route.source_qualification_route_digest != source_digest
        or subgoal_route.route_role != "task_subgoal_navigation"
        or fallback_route.route_role != "target_independent_fallback"
    ):
        raise ValueError("FloorPlan17 route role/source mismatch")
    configuration = FrozenR2Configuration(
        configuration_id=CONFIGURATION_ID,
        scene=str(public["scene"]),
        private_configuration_set_digest=stable_digest(private),
        start_pose_digest=str(public["start_pose_digest"]),
        source_qualification_digest=source_digest,
        subgoal_route_id=subgoal_route.route_id,
        fallback_route_id=fallback_route.route_id,
        target_cup_object_id=str(private.get("target_cup_object_id", "")),
        coffee_machine_object_id=str(private.get("coffee_machine_object_id", "")),
        start_action=deepcopy(dict(start_action)),
    )
    if not configuration.target_cup_object_id or not configuration.coffee_machine_object_id:
        raise ValueError("FloorPlan17 private target identity is missing")
    return FrozenR2Runtime(
        configuration=configuration,
        subgoal_route=subgoal_route,
        fallback_route=fallback_route,
    )


def validate_gate_config(config: Mapping[str, Any]) -> None:
    expected = {
        "gate_version": GATE_VERSION,
        "configuration_id": CONFIGURATION_ID,
        "scene": "FloorPlan17",
        "task": "thor_cup_after_coffee_subgoal",
        "memory": "no_memory",
        "max_steps": 2048,
        "mode": "formal",
        "included_in_formal_aggregate": False,
        "save_frames": False,
        "trace_html": False,
        "visualize": False,
        "save_evaluator_debug": False,
        "formal_execution_authorized": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"FloorPlan17 production gate mismatch: {key}")
    if _sha256(PRIVATE_CANDIDATE) != str(config.get("private_candidate_sha256", "")):
        raise ValueError("FloorPlan17 private candidate changed")
    frozen = config.get("historical_artifacts_frozen", {})
    if not isinstance(frozen, Mapping) or not frozen:
        raise ValueError("FloorPlan17 production gate frozen sources missing")
    for relative, digest in frozen.items():
        path = (PROJECT_ROOT / str(relative)).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise ValueError("FloorPlan17 production gate source outside project") from exc
        if not path.is_file() or _sha256(path) != str(digest):
            raise ValueError(f"FloorPlan17 production gate source changed: {relative}")


def _audit_episode(
    *, summary: Mapping[str, Any], episode_dir: Path, runtime: FrozenR2Runtime
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    expected = {
        "success": True,
        "failure_reason": "",
        "setup_completed": True,
        "setup_failure_reason": "",
        "information_boundary_passed": True,
        "included_in_formal_aggregate": False,
        "shared_search_route_id": runtime.fallback_route.route_id,
        "shared_search_action_sequence_digest": (
            runtime.fallback_route.action_sequence_digest
        ),
        "shared_subgoal_route_id": runtime.subgoal_route.route_id,
        "shared_subgoal_action_sequence_digest": (
            runtime.subgoal_route.action_sequence_digest
        ),
        "shared_search_action_failure_count": 0,
        "shared_subgoal_action_failure_count": 0,
        "shared_search_route_entry_mismatch_count": 0,
        "shared_subgoal_route_entry_mismatch_count": 0,
        "shared_route_action_recovery_attempt_count": 0,
        "shared_route_action_recovery_action_count": 0,
        "shared_route_action_recovered_failure_count": 0,
        "shared_route_action_recovery_terminal_failure_count": 0,
        "shared_route_action_recovery_pending_action_count": 0,
        "invalid_planner_decision_count": 0,
        "target_lock_terminal_failure_count": 0,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"summary:{key}")
    if not isinstance(summary.get("steps"), int) or int(summary["steps"]) > 2048:
        errors.append("summary:steps")
    progress = summary.get("task_progress", {})
    if not isinstance(progress, Mapping) or progress.get("ordered_subgoal_passed") is not True:
        errors.append("summary:ordered_subgoal_passed")
    trace = [
        json.loads(line)
        for line in (episode_dir / "episode.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    recovery_phases = []
    for row in trace:
        shared = row.get("planner_input", {}).get("request", {}).get("shared_search")
        if isinstance(shared, Mapping) and str(shared.get("phase", "")).startswith(
            "route_action_"
        ):
            recovery_phases.append(str(shared.get("phase", "")))
    if recovery_phases:
        errors.append("trace:route_action_recovery_used")
    return errors, {
        "shared_subgoal_coverage_action_count": summary.get(
            "shared_subgoal_coverage_action_count"
        ),
        "shared_search_coverage_action_count": summary.get(
            "shared_search_coverage_action_count"
        ),
        "invalid_action_count": summary.get("invalid_action_count"),
        "target_lock_interaction_recovery_action_count": summary.get(
            "target_lock_interaction_recovery_action_count"
        ),
        "route_action_recovery_phases": recovery_phases,
    }


def run_gate(*, config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_gate_config(config)
    head, upstream, dirty = _git_state()
    if dirty or head != upstream:
        raise ValueError("FloorPlan17 production gate requires a clean pushed HEAD")
    if output_dir.exists():
        raise ValueError("FloorPlan17 production gate output already exists")
    runtime = load_candidate_runtime()
    output_dir.mkdir(parents=True)
    episode_dir = output_dir / "no_memory"
    summary = ThorEpisodeRunner(
        ThorEpisodeConfig(
            task=str(config["task"]),
            scene=str(config["scene"]),
            planner="deterministic",
            memory="no_memory",
            search_route_id=runtime.fallback_route.route_id,
            subgoal_route_id=runtime.subgoal_route.route_id,
            condition="stable",
            mode="formal",
            max_steps=int(config["max_steps"]),
            output_dir=episode_dir,
            save_frames=False,
            trace_html=False,
            visualize=False,
            save_evaluator_debug=False,
            included_in_formal_aggregate=False,
            run_purpose="phase5_r2_floorplan17_production_equivalent_gate_v1",
        ),
        search_route=runtime.fallback_route,
        subgoal_route=runtime.subgoal_route,
        evaluator_setup=runtime.configuration,
    ).run()
    errors, metrics = _audit_episode(
        summary=summary, episode_dir=episode_dir, runtime=runtime
    )
    result = {
        "gate_version": GATE_VERSION,
        "code_revision": head,
        "working_tree_dirty": False,
        "configuration_id": CONFIGURATION_ID,
        "memory": "no_memory",
        "included_in_formal_aggregate": False,
        "passed": not errors,
        "success": summary.get("success"),
        "steps": summary.get("steps"),
        "information_boundary_passed": summary.get("information_boundary_passed"),
        "shared_search_action_failure_count": summary.get(
            "shared_search_action_failure_count"
        ),
        "shared_subgoal_action_failure_count": summary.get(
            "shared_subgoal_action_failure_count"
        ),
        "shared_route_action_recovery_attempt_count": summary.get(
            "shared_route_action_recovery_attempt_count"
        ),
        "shared_route_action_recovery_action_count": summary.get(
            "shared_route_action_recovery_action_count"
        ),
        "shared_route_action_recovery_terminal_failure_count": summary.get(
            "shared_route_action_recovery_terminal_failure_count"
        ),
        **metrics,
        "audit_errors": errors,
        "claim_boundary": config["claim_boundary"],
        "next_gate": (
            "freeze FloorPlan17 as the conservative R2 replacement and build runtime-v3"
            if not errors
            else "stop and classify FloorPlan17 production-equivalent failure"
        ),
    }
    public_text = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if any(token in public_text for token in FORBIDDEN_PUBLIC_TOKENS):
        raise ValueError("FloorPlan17 production gate public result contains private material")
    _write_json(output_dir / "gate_summary.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_gate(
            config_path=args.config.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
        )
    except (
        json.JSONDecodeError, OSError, subprocess.SubprocessError,
        TypeError, ValueError,
    ) as exc:
        print(f"phase5_r2_floorplan17_production_gate_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

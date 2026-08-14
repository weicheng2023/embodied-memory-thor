#!/usr/bin/env python3
"""Run one excluded FloorPlan10 shared-route-action recovery gate."""

from __future__ import annotations

import argparse
import hashlib
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
from embodied_memory_thor.phase5.frozen_r2_v2 import (  # noqa: E402
    load_frozen_r2_runtime_v2,
)
from embodied_memory_thor.phase5.search import (  # noqa: E402
    SHARED_ROUTE_ACTION_RECOVERY_ACTION_LIMIT,
    SHARED_ROUTE_ACTION_RECOVERY_ATTEMPT_LIMIT,
    SHARED_ROUTE_ACTION_RECOVERY_POLICY_VERSION,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "phase5_r2_floorplan10_route_action_recovery_gate_v1.json"
)
GATE_VERSION = "phase5-r2-floorplan10-route-action-recovery-gate-v1"
CONFIGURATION_ID = "FloorPlan10_R2_fixed_start_001"
EXPECTED_FAILED_ACTION_INDEX = 200
EXPECTED_ACTIONS = ("MoveAhead", "Pass", "MoveAhead")
EXPECTED_PHASES = (
    "coverage",
    "route_action_stabilization",
    "route_action_retry",
)
EXPECTED_SUCCESSES = (False, True, True)
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
            ["git", *args],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    return (
        value("rev-parse", "HEAD"),
        value("rev-parse", "@{upstream}"),
        bool(value("status", "--porcelain")),
    )


def validate_gate_config(config: Mapping[str, Any]) -> None:
    expected = {
        "gate_version": GATE_VERSION,
        "configuration_id": CONFIGURATION_ID,
        "scene": "FloorPlan10",
        "task": "thor_cup_after_coffee_subgoal",
        "panel": "r2_stable",
        "condition": "stable",
        "memory": "no_memory",
        "route_action_recovery_policy": (
            SHARED_ROUTE_ACTION_RECOVERY_POLICY_VERSION
        ),
        "route_action_recovery_attempt_limit": (
            SHARED_ROUTE_ACTION_RECOVERY_ATTEMPT_LIMIT
        ),
        "route_action_recovery_action_limit": (
            SHARED_ROUTE_ACTION_RECOVERY_ACTION_LIMIT
        ),
        "expected_failed_action_index": EXPECTED_FAILED_ACTION_INDEX,
        "max_steps": 2048,
        "mode": "formal",
        "run_purpose": "phase5_r2_floorplan10_route_action_recovery_gate_v1",
        "included_in_formal_aggregate": False,
        "save_frames": False,
        "trace_html": False,
        "visualize": False,
        "save_evaluator_debug": False,
        "formal_execution_authorized": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"route-action recovery gate mismatch: {key}")
    if tuple(config.get("expected_actions", ())) != EXPECTED_ACTIONS:
        raise ValueError("route-action recovery gate action sequence mismatch")
    if tuple(config.get("expected_phases", ())) != EXPECTED_PHASES:
        raise ValueError("route-action recovery gate phase sequence mismatch")
    frozen = config.get("historical_artifacts_frozen", {})
    if not isinstance(frozen, Mapping) or not frozen:
        raise ValueError("route-action recovery gate frozen artifacts missing")
    for relative, digest in frozen.items():
        path = (PROJECT_ROOT / str(relative)).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise ValueError("route-action recovery gate source outside project") from exc
        if not path.is_file() or _sha256(path) != str(digest):
            raise ValueError(f"route-action recovery gate source changed: {relative}")


def _audit_episode(
    *, summary: Mapping[str, Any], episode_dir: Path
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    expected_summary = {
        "success": True,
        "failure_reason": "",
        "setup_completed": True,
        "setup_failure_reason": "",
        "information_boundary_passed": True,
        "included_in_formal_aggregate": False,
        "shared_route_action_recovery_policy": (
            SHARED_ROUTE_ACTION_RECOVERY_POLICY_VERSION
        ),
        "shared_route_action_recovery_attempt_limit": (
            SHARED_ROUTE_ACTION_RECOVERY_ATTEMPT_LIMIT
        ),
        "shared_route_action_recovery_action_limit": (
            SHARED_ROUTE_ACTION_RECOVERY_ACTION_LIMIT
        ),
        "shared_route_action_recovery_attempt_count": 1,
        "shared_route_action_recovery_action_count": 2,
        "shared_route_action_recovered_failure_count": 1,
        "shared_route_action_recovery_terminal_failure_count": 0,
        "shared_route_action_recovery_pending_action_count": 0,
        "shared_search_action_failure_count": 0,
        "invalid_planner_decision_count": 0,
        "invalid_action_count": 1,
    }
    for key, value in expected_summary.items():
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
    matched_rows = []
    for row in trace:
        shared = row.get("planner_input", {}).get("request", {}).get("shared_search")
        if not isinstance(shared, Mapping):
            continue
        if (
            shared.get("action_index") == EXPECTED_FAILED_ACTION_INDEX
            and shared.get("phase") in EXPECTED_PHASES
        ):
            matched_rows.append(row)
    phases = tuple(
        str(row["planner_input"]["request"]["shared_search"].get("phase", ""))
        for row in matched_rows
    )
    actions = tuple(
        str(row.get("planner_decision", {}).get("action", {}).get("action", ""))
        for row in matched_rows
    )
    successes = tuple(
        row.get("environment_feedback", {}).get("action_success")
        for row in matched_rows
    )
    if phases != EXPECTED_PHASES:
        errors.append("route_action_recovery_phases")
    if actions != EXPECTED_ACTIONS:
        errors.append("route_action_recovery_actions")
    if successes != EXPECTED_SUCCESSES:
        errors.append("route_action_recovery_results")
    for row in matched_rows[1:]:
        directive = row["planner_input"]["request"]["shared_search"]
        if set(directive) != {
            "action",
            "action_index",
            "action_sequence_digest",
            "phase",
            "policy",
            "route_id",
            "route_role",
        }:
            errors.append("route_action_recovery_directive_boundary")
            break

    return errors, {
        "failed_action_index": EXPECTED_FAILED_ACTION_INDEX,
        "route_action_recovery_phases": list(phases),
        "route_action_recovery_actions": list(actions),
        "route_action_recovery_action_successes": list(successes),
        "recovery_directives_public_schema_only": (
            "route_action_recovery_directive_boundary" not in errors
        ),
    }


def run_gate(*, config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_gate_config(config)
    head, upstream, dirty = _git_state()
    if dirty or head != upstream:
        raise ValueError("route-action recovery gate requires a clean pushed HEAD")
    if output_dir.exists():
        raise ValueError("route-action recovery gate output already exists")

    runtime = load_frozen_r2_runtime_v2(CONFIGURATION_ID)
    public = runtime.configuration.public_reference()
    if config.get("scene") != public.get("scene"):
        raise ValueError("route-action recovery runtime scene mismatch")
    expected_routes = {
        "fallback_route_id": runtime.fallback_route.route_id,
        "fallback_route_action_sequence_digest": (
            runtime.fallback_route.action_sequence_digest
        ),
        "subgoal_route_id": runtime.subgoal_route.route_id,
        "subgoal_route_action_sequence_digest": (
            runtime.subgoal_route.action_sequence_digest
        ),
    }
    for key, value in expected_routes.items():
        if config.get(key) != value:
            raise ValueError(f"route-action recovery runtime mismatch: {key}")

    output_dir.mkdir(parents=True)
    episode_dir = output_dir / "no_memory"
    summary = ThorEpisodeRunner(
        ThorEpisodeConfig(
            task=str(config["task"]),
            scene=str(config["scene"]),
            planner="deterministic",
            memory="no_memory",
            search_route_id=runtime.fallback_route.route_id,
            condition="stable",
            mode="formal",
            max_steps=int(config["max_steps"]),
            output_dir=episode_dir,
            save_frames=False,
            trace_html=False,
            visualize=False,
            save_evaluator_debug=False,
            included_in_formal_aggregate=False,
            run_purpose=str(config["run_purpose"]),
        ),
        search_route=runtime.fallback_route,
        subgoal_route=runtime.subgoal_route,
        evaluator_setup=runtime.configuration,
    ).run()
    errors, trace_summary = _audit_episode(summary=summary, episode_dir=episode_dir)
    result = {
        "gate_version": GATE_VERSION,
        "code_revision": head,
        "working_tree_dirty": False,
        "configuration_id": CONFIGURATION_ID,
        "memory": "no_memory",
        "route_action_recovery_policy": (
            SHARED_ROUTE_ACTION_RECOVERY_POLICY_VERSION
        ),
        "included_in_formal_aggregate": False,
        "passed": not errors,
        "success": summary.get("success"),
        "steps": summary.get("steps"),
        "invalid_action_count": summary.get("invalid_action_count"),
        "recovery_attempt_count": summary.get(
            "shared_route_action_recovery_attempt_count"
        ),
        "recovery_action_count": summary.get(
            "shared_route_action_recovery_action_count"
        ),
        "recovered_failure_count": summary.get(
            "shared_route_action_recovered_failure_count"
        ),
        "terminal_failure_count": summary.get(
            "shared_route_action_recovery_terminal_failure_count"
        ),
        "information_boundary_passed": summary.get(
            "information_boundary_passed"
        ),
        **trace_summary,
        "audit_errors": errors,
        "claim_boundary": config["claim_boundary"],
        "next_gate": (
            "freeze excluded gate evidence and design a fresh formal-v5 readiness protocol"
            if not errors
            else "stop and diagnose the FloorPlan10 route-action recovery isolation failure"
        ),
    }
    public_text = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if any(token in public_text for token in FORBIDDEN_PUBLIC_TOKENS):
        raise ValueError("route-action recovery public result contains private material")
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
        json.JSONDecodeError,
        OSError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"phase5_r2_route_action_recovery_gate_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run one excluded FloorPlan306 target-lock-v2 recovery isolation gate."""

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
from embodied_memory_thor.phase4.task import (  # noqa: E402
    PHASE5_BOOK_DISTRACTION_POLICY_V4,
)
from embodied_memory_thor.phase5.frozen_r1 import (  # noqa: E402
    load_frozen_r1_runtime,
)
from embodied_memory_thor.phase5.target_lock import (  # noqa: E402
    TARGET_LOCK_CANONICAL_PICKUP_HORIZON_DEGREES,
    TARGET_LOCK_INTERACTION_RECOVERY_ACTION_LIMIT,
    TARGET_LOCK_INTERACTION_RECOVERY_RETRY_LIMIT,
    TARGET_LOCK_POLICY_VERSION,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "phase5_r1_target_lock_recovery_gate_v2.json"
)
GATE_VERSION = "phase5-r1-target-lock-interaction-recovery-gate-v2"
CONFIGURATION_ID = "FloorPlan306_R1_fixed_start_001"
EXPECTED_TARGET_LOCK_ACTIONS = ("PickupObject", "LookUp", "PickupObject")
FORBIDDEN_PUBLIC_TOKENS = (
    "Book|",
    "target_point",
    "anchor_id",
    "objectId",
    "PlaceObjectAtPoint",
    "TeleportFull",
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
        "scene": "FloorPlan306",
        "task": "thor_book_reacquire_k2",
        "panel": "r1_stable",
        "condition": "stable",
        "memory": "object_memory",
        "book_distraction_policy": PHASE5_BOOK_DISTRACTION_POLICY_V4,
        "target_lock_policy": TARGET_LOCK_POLICY_VERSION,
        "canonical_pickup_horizon_degrees": (
            TARGET_LOCK_CANONICAL_PICKUP_HORIZON_DEGREES
        ),
        "interaction_recovery_action_limit": (
            TARGET_LOCK_INTERACTION_RECOVERY_ACTION_LIMIT
        ),
        "interaction_recovery_retry_limit": (
            TARGET_LOCK_INTERACTION_RECOVERY_RETRY_LIMIT
        ),
        "max_steps": 64,
        "mode": "formal",
        "run_purpose": "phase5_r1_target_lock_interaction_recovery_gate_v2",
        "included_in_formal_aggregate": False,
        "save_frames": False,
        "trace_html": False,
        "visualize": False,
        "save_evaluator_debug": False,
        "formal_execution_authorized": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"target-lock recovery gate mismatch: {key}")
    if tuple(config.get("expected_target_lock_actions", ())) != (
        EXPECTED_TARGET_LOCK_ACTIONS
    ):
        raise ValueError("target-lock recovery gate action sequence mismatch")
    frozen = config.get("historical_artifacts_frozen", {})
    if not isinstance(frozen, Mapping) or not frozen:
        raise ValueError("target-lock recovery gate frozen artifacts missing")
    for relative, digest in frozen.items():
        path = (PROJECT_ROOT / str(relative)).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise ValueError("target-lock recovery gate source outside project") from exc
        if not path.is_file() or _sha256(path) != str(digest):
            raise ValueError(f"target-lock recovery gate source changed: {relative}")


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
        "book_distraction_policy": PHASE5_BOOK_DISTRACTION_POLICY_V4,
        "policy": TARGET_LOCK_POLICY_VERSION,
        "target_lock_pickup_attempt_count": 2,
        "target_lock_interaction_recovery_action_count": 1,
        "target_lock_interaction_recovery_attempt_count": 1,
        "target_lock_terminal_failure_count": 0,
        "target_lock_failed_reason": "",
        "failed_interaction_count": 1,
        "invalid_action_count": 1,
    }
    for key, value in expected_summary.items():
        if summary.get(key) != value:
            errors.append(f"summary:{key}")
    if not isinstance(summary.get("steps"), int) or int(summary["steps"]) > 64:
        errors.append("summary:steps")

    trace = [
        json.loads(line)
        for line in (episode_dir / "episode.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    target_lock_rows = [
        row
        for row in trace
        if str(row.get("planner_decision", {}).get("reason_code", "")).startswith(
            "target_lock_"
        )
    ]
    actions = tuple(
        str(row.get("planner_decision", {}).get("action", {}).get("action", ""))
        for row in target_lock_rows
    )
    successes = tuple(
        row.get("environment_feedback", {}).get("action_success")
        for row in target_lock_rows
    )
    horizons = tuple(
        round(
            float(
                row.get("planner_input", {})
                .get("request", {})
                .get("observation", {})
                .get("agent", {})
                .get("cameraHorizon", 999.0)
            ),
            3,
        )
        for row in target_lock_rows
    )
    if actions != EXPECTED_TARGET_LOCK_ACTIONS:
        errors.append("target_lock_actions")
    if successes != (False, True, True):
        errors.append("target_lock_action_results")
    if horizons != (0.0, 0.0, -30.0):
        errors.append("target_lock_horizons")
    recovery_row = target_lock_rows[1] if len(target_lock_rows) == 3 else {}
    recovery_action = recovery_row.get("planner_decision", {}).get("action", {})
    if set(recovery_action) != {"action"}:
        errors.append("interaction_recovery_action_boundary")

    ordinary = json.dumps(trace, ensure_ascii=False, sort_keys=True)
    for forbidden in ("PlaceObjectAtPoint", "TeleportFull", "target_point"):
        if forbidden in ordinary:
            errors.append(f"ordinary_private_leak:{forbidden}")
    public_trace_summary = {
        "target_lock_actions": list(actions),
        "target_lock_action_successes": list(successes),
        "target_lock_camera_horizons_degrees": list(horizons),
        "interaction_recovery_action_contains_only_action_name": (
            set(recovery_action) == {"action"}
        ),
    }
    return errors, public_trace_summary


def run_gate(*, config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_gate_config(config)
    head, upstream, dirty = _git_state()
    if dirty or head != upstream:
        raise ValueError("target-lock recovery gate requires a clean pushed HEAD")
    if output_dir.exists():
        raise ValueError("target-lock recovery gate output already exists")

    runtime = load_frozen_r1_runtime(CONFIGURATION_ID)
    public = runtime.configuration.public_reference()
    for key in ("scene", "search_route_id"):
        if str(config.get(key, "")) != str(public.get(key, "")):
            raise ValueError(f"target-lock recovery runtime mismatch: {key}")
    if config.get("search_route_action_sequence_digest") != (
        runtime.search_route.action_sequence_digest
    ):
        raise ValueError("target-lock recovery route digest mismatch")

    output_dir.mkdir(parents=True)
    episode_dir = output_dir / "object_memory"
    summary = ThorEpisodeRunner(
        ThorEpisodeConfig(
            task=str(config["task"]),
            scene=str(config["scene"]),
            planner="deterministic",
            memory="object_memory",
            book_distraction_policy=str(config["book_distraction_policy"]),
            search_route_id=runtime.search_route.route_id,
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
        search_route=runtime.search_route,
        evaluator_setup=runtime.configuration,
    ).run()
    errors, trace_summary = _audit_episode(summary=summary, episode_dir=episode_dir)
    passed = not errors
    result = {
        "gate_version": GATE_VERSION,
        "code_revision": head,
        "working_tree_dirty": False,
        "configuration_id": CONFIGURATION_ID,
        "memory": "object_memory",
        "target_lock_policy": TARGET_LOCK_POLICY_VERSION,
        "included_in_formal_aggregate": False,
        "passed": passed,
        "success": summary.get("success"),
        "steps": summary.get("steps"),
        "invalid_action_count": summary.get("invalid_action_count"),
        "failed_interaction_count": summary.get("failed_interaction_count"),
        "interaction_recovery_action_count": summary.get(
            "target_lock_interaction_recovery_action_count"
        ),
        "interaction_recovery_attempt_count": summary.get(
            "target_lock_interaction_recovery_attempt_count"
        ),
        "terminal_failure_count": summary.get(
            "target_lock_terminal_failure_count"
        ),
        "information_boundary_passed": summary.get(
            "information_boundary_passed"
        ),
        **trace_summary,
        "audit_errors": errors,
        "claim_boundary": config["claim_boundary"],
        "next_gate": (
            "freeze excluded gate evidence and design a fresh formal-v4 readiness protocol"
            if passed
            else "stop and diagnose the target-lock-v2 isolation failure"
        ),
    }
    public_text = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if any(token in public_text for token in FORBIDDEN_PUBLIC_TOKENS):
        raise ValueError("target-lock recovery public result contains private material")
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
        print(f"phase5_r1_target_lock_recovery_gate_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

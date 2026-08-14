#!/usr/bin/env python3
"""Run the excluded FloorPlan303 fixed-distraction successor gate."""

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

from embodied_memory_thor.phase4.runner import (  # noqa: E402
    ThorEpisodeConfig,
    ThorEpisodeRunner,
)
from embodied_memory_thor.phase4.task import (  # noqa: E402
    PHASE5_BOOK_DISTRACTION_POLICY_V2,
    PHASE5_BOOK_DISTRACTION_POLICY_V3,
)
from embodied_memory_thor.phase5.frozen_r1 import (  # noqa: E402
    load_frozen_r1_runtime,
)
from embodied_memory_thor.phase5.protocol import PHASE5_VARIANTS  # noqa: E402
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "phase5_r1_distraction_successor_gate_v1.json"
)
EXPECTED_ACTIONS = ("RotateRight", "RotateRight", "LookDown", "LookUp")
EXPECTED_ACTIONS_BY_POLICY = {
    PHASE5_BOOK_DISTRACTION_POLICY_V2: EXPECTED_ACTIONS,
    PHASE5_BOOK_DISTRACTION_POLICY_V3: ("RotateRight", "RotateRight", "Pass"),
}
GATE_VERSION_BY_POLICY = {
    PHASE5_BOOK_DISTRACTION_POLICY_V2: "phase5-r1-distraction-successor-gate-v1",
    PHASE5_BOOK_DISTRACTION_POLICY_V3: "phase5-r1-distraction-successor-gate-v2",
}


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

    head = value("rev-parse", "HEAD")
    upstream = value("rev-parse", "@{upstream}")
    dirty = bool(value("status", "--porcelain"))
    return head, upstream, dirty


def validate_gate_config(config: Mapping[str, Any]) -> None:
    policy = str(config.get("book_distraction_policy", ""))
    if policy not in EXPECTED_ACTIONS_BY_POLICY:
        raise ValueError("gate distraction policy mismatch")
    if config.get("gate_version") != GATE_VERSION_BY_POLICY[policy]:
        raise ValueError("gate version mismatch")
    if (
        config.get("task") != "thor_book_reacquire_k2"
        or config.get("panel") != "r1_stable"
        or config.get("condition") != "stable"
    ):
        raise ValueError("gate task/panel/condition mismatch")
    if tuple(config.get("variants", ())) != PHASE5_VARIANTS:
        raise ValueError("gate variant order mismatch")
    expected_actions = EXPECTED_ACTIONS_BY_POLICY[policy]
    if tuple(config.get("expected_actions", ())) != expected_actions:
        raise ValueError("gate action template mismatch")
    if config.get("max_steps") != len(expected_actions):
        raise ValueError("gate must stop exactly after the distraction template")
    for key in (
        "save_frames",
        "trace_html",
        "visualize",
        "save_evaluator_debug",
        "included_in_formal_aggregate",
    ):
        if config.get(key) is not False:
            raise ValueError(f"gate output policy mismatch: {key}")


def _audit_episode(
    *, summary: Mapping[str, Any], episode_dir: Path, expected_actions: tuple[str, ...]
) -> list[str]:
    errors: list[str] = []
    progress = summary.get("task_progress", {})
    if summary.get("success") is not False:
        errors.append("unexpected_task_success")
    if summary.get("failure_reason") != "max_steps_exceeded":
        errors.append("unexpected_terminal_reason")
    if summary.get("steps") != len(expected_actions):
        errors.append("evaluated_action_count")
    if summary.get("setup_completed") is not True or summary.get(
        "setup_failure_reason"
    ):
        errors.append("setup_failed")
    if summary.get("information_boundary_passed") is not True:
        errors.append("information_boundary_failed")
    if summary.get("included_in_formal_aggregate") is not False:
        errors.append("formal_aggregate_label")
    if not isinstance(progress, Mapping):
        errors.append("task_progress_missing")
    else:
        if progress.get("distraction_policy") != summary.get(
            "book_distraction_policy"
        ):
            errors.append("progress_policy")
        if progress.get("distraction_transition_count") != len(expected_actions):
            errors.append("transition_count")
        if progress.get("stage") != "reacquire_book":
            errors.append("post_template_stage")
        if progress.get("distraction_error"):
            errors.append("distraction_error")
        if not isinstance(progress.get("book_hidden_step"), int):
            errors.append("book_not_hidden")
        if progress.get("short_memory_k2_eviction_ready") is not True:
            errors.append("k2_eviction_not_ready")

    trace_path = episode_dir / "episode.jsonl"
    records = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    actions = tuple(
        str(row.get("planner_decision", {}).get("action", {}).get("action", ""))
        for row in records
    )
    if actions != expected_actions:
        errors.append("action_template")
    if any(
        row.get("environment_feedback", {}).get("action_success") is not True
        for row in records
    ):
        errors.append("native_action_failure")
    ordinary = json.dumps(records, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "PlaceObjectAtPoint",
        "TeleportFull",
        "target_point",
        "reachable_positions",
    ):
        if forbidden in ordinary:
            errors.append(f"ordinary_private_leak:{forbidden}")
    return errors


def run_gate(*, config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_gate_config(config)
    expected_actions = EXPECTED_ACTIONS_BY_POLICY[
        str(config["book_distraction_policy"])
    ]
    head, upstream, dirty = _git_state()
    if dirty or head != upstream:
        raise ValueError("distraction gate requires a clean pushed HEAD")
    if output_dir.exists():
        raise ValueError("gate output directory already exists")
    runtime = load_frozen_r1_runtime(str(config["configuration_id"]))
    public = runtime.configuration.public_reference()
    for key in ("scene", "search_route_id"):
        if str(config.get(key, "")) != str(public.get(key, "")):
            raise ValueError(f"gate frozen runtime mismatch: {key}")
    if config.get("search_route_action_sequence_digest") != (
        runtime.search_route.action_sequence_digest
    ):
        raise ValueError("gate search route digest mismatch")

    output_dir.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    for variant in PHASE5_VARIANTS:
        episode_dir = output_dir / variant
        summary = ThorEpisodeRunner(
            ThorEpisodeConfig(
                task=str(config["task"]),
                scene=str(config["scene"]),
                planner="deterministic",
                memory=variant,
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
        errors = _audit_episode(
            summary=summary,
            episode_dir=episode_dir,
            expected_actions=expected_actions,
        )
        rows.append(
            {
                "variant": variant,
                "evaluated_action_count": summary.get("steps"),
                "distraction_transition_count": summary.get(
                    "task_progress", {}
                ).get("distraction_transition_count"),
                "book_hidden": isinstance(
                    summary.get("task_progress", {}).get("book_hidden_step"), int
                ),
                "post_template_stage": summary.get("task_progress", {}).get("stage"),
                "information_boundary_passed": summary.get(
                    "information_boundary_passed"
                ),
                "audit_errors": errors,
            }
        )
        if errors:
            break
    passed = len(rows) == len(PHASE5_VARIANTS) and all(
        not row["audit_errors"] for row in rows
    )
    result = {
        "gate_version": config["gate_version"],
        "code_revision": head,
        "working_tree_dirty": False,
        "configuration_id": config["configuration_id"],
        "book_distraction_policy": config["book_distraction_policy"],
        "included_in_formal_aggregate": False,
        "passed": passed,
        "completed_variant_count": len(rows),
        "rows": rows,
        "claim_boundary": config["claim_boundary"],
        "next_gate": (
            "version a fresh full formal protocol and rerun from cell 1"
            if passed
            else "stop and diagnose the fixed-template distraction gate"
        ),
    }
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
    except (json.JSONDecodeError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"phase5_r1_distraction_gate_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

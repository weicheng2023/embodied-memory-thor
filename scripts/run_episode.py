#!/usr/bin/env python3
"""Run one state-evaluated embodied episode and write structured logs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.actions import ActionExecutor, ActionSpace  # noqa: E402
from embodied_memory_thor.env import MockEnv, ThorEnv  # noqa: E402
from embodied_memory_thor.env.object_parser import parse_objects  # noqa: E402
from embodied_memory_thor.evaluation import (  # noqa: E402
    check_object_availability,
    evaluate_task_success,
    load_task,
)
from embodied_memory_thor.logging_utils import EpisodeLogger, create_episode_dir  # noqa: E402
from embodied_memory_thor.planners import RuleBasedPlanner  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """Build episode command-line arguments."""

    parser = argparse.ArgumentParser(description="Run one embodied-agent episode.")
    parser.add_argument("--task", required=True, help="task name from configs/tasks.yaml")
    parser.add_argument("--scene", help="scene name; defaults by environment mode")
    parser.add_argument(
        "--planner",
        default="rule_based",
        choices=("rule_based",),
        help="planner implementation",
    )
    parser.add_argument("--mock", action="store_true", help="use the deterministic mock kitchen")
    parser.add_argument("--max-steps", type=int, help="override the configured positive step limit")
    parser.add_argument("--output-dir", help="explicit episode output directory")
    parser.add_argument("--tasks-config", help="optional alternative tasks YAML file")
    return parser


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summary_template(args: argparse.Namespace, scene: str, output_dir: Path) -> dict[str, Any]:
    return {
        "task": args.task,
        "scene": scene,
        "planner": args.planner,
        "mode": "mock" if args.mock else "ai2thor",
        "success": False,
        "steps": 0,
        "invalid_action_count": 0,
        "invalid_action_rate": 0.0,
        "llm_calls": 0,
        "average_planning_latency_seconds": 0.0,
        "total_episode_latency_seconds": 0.0,
        "failure_reason": "",
        "output_dir": str(output_dir),
        "started_at": _utc_now(),
    }


def main(argv: list[str] | None = None) -> int:
    """Execute an episode and return zero only when its state goal succeeds."""

    args = build_parser().parse_args(argv)
    if args.max_steps is not None and args.max_steps <= 0:
        print("--max-steps must be a positive integer", file=sys.stderr)
        return 2

    try:
        task = load_task(args.task, args.tasks_config)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as exc:
        print(f"Task configuration error: {exc}", file=sys.stderr)
        return 2

    max_steps = args.max_steps or task.max_steps
    scene = args.scene or (MockEnv.DEFAULT_SCENE if args.mock else "FloorPlan1")
    mode = "mock" if args.mock else "ai2thor"
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else create_episode_dir(task_name=task.task_name, planner_name=args.planner, mode=mode)
    )
    logger = EpisodeLogger(output_dir)
    summary = _summary_template(args, scene, output_dir)

    env = MockEnv() if args.mock else ThorEnv()
    planner = RuleBasedPlanner()
    action_space = ActionSpace()
    executor = ActionExecutor(action_space)
    current_event: Any | None = None
    planning_latencies: list[float] = []
    invalid_action_count = 0
    episode_start = perf_counter()
    unmet_conditions: tuple[str, ...] = ()

    try:
        current_event = env.reset(scene)
        availability = check_object_availability(task, current_event)
        if not availability.available:
            missing = ", ".join(availability.missing_object_types)
            summary["failure_reason"] = f"missing_required_objects: {missing}"
        else:
            success_result = evaluate_task_success(task, current_event)
            unmet_conditions = success_result.unmet_conditions
            summary["success"] = success_result.success

            for step_number in range(1, max_steps + 1):
                if summary["success"]:
                    break

                planning_start = perf_counter()
                action = planner.plan(task, current_event, memory=None, action_space=action_space)
                planning_latency = perf_counter() - planning_start
                planning_latencies.append(planning_latency)

                if action is None:
                    summary["failure_reason"] = "planner_returned_no_action"
                    break

                action_start = perf_counter()
                execution = executor.execute(env, action)
                action_latency = perf_counter() - action_start
                if execution.event is not None:
                    current_event = execution.event
                if execution.invalid_action:
                    invalid_action_count += 1

                success_result = evaluate_task_success(task, current_event)
                unmet_conditions = success_result.unmet_conditions
                summary["success"] = success_result.success
                summary["steps"] = step_number

                logger.log_step(
                    {
                        "timestamp": _utc_now(),
                        "step": step_number,
                        "action": execution.action,
                        "success": execution.success,
                        "error": execution.error_message,
                        "invalid_action": execution.invalid_action,
                        "visible_objects": parse_objects(current_event, visible_only=True),
                        "memory_snapshot": {},
                        "planning_latency_seconds": planning_latency,
                        "action_latency_seconds": action_latency,
                        "task_success_after_action": success_result.success,
                        "unmet_goal_conditions": list(success_result.unmet_conditions),
                    }
                )

            if not summary["success"] and not summary["failure_reason"]:
                detail = "; ".join(unmet_conditions) or "goal conditions not satisfied"
                summary["failure_reason"] = f"max_steps_exceeded: {detail}"
    except Exception as exc:
        summary["failure_reason"] = f"environment_error: {type(exc).__name__}: {exc}"
    finally:
        env.close()

    summary["invalid_action_count"] = invalid_action_count
    steps = int(summary["steps"])
    summary["invalid_action_rate"] = invalid_action_count / steps if steps else 0.0
    summary["average_planning_latency_seconds"] = (
        sum(planning_latencies) / len(planning_latencies) if planning_latencies else 0.0
    )
    summary["total_episode_latency_seconds"] = perf_counter() - episode_start
    summary["finished_at"] = _utc_now()
    if summary["success"]:
        summary["failure_reason"] = ""

    logger.write_summary(summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    print(f"episode_log: {logger.episode_path}")
    print(f"summary: {logger.summary_path}")
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

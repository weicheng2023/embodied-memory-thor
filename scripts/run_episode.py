#!/usr/bin/env python3
"""Run one state-evaluated embodied episode and write structured logs."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.actions import ActionExecutor, ActionSpace  # noqa: E402
from embodied_memory_thor.env import MockEnv, ThorEnv  # noqa: E402
from embodied_memory_thor.env.object_parser import parse_objects  # noqa: E402
from embodied_memory_thor.evaluation import (  # noqa: E402
    TaskProgressTracker,
    check_object_availability,
    evaluate_task_success,
    load_task,
)
from embodied_memory_thor.logging_utils import EpisodeLogger, create_episode_dir  # noqa: E402
from embodied_memory_thor.memory import ActionLog, MemoryHint, build_memory_provider  # noqa: E402
from embodied_memory_thor.planners import (  # noqa: E402
    MemoryAwarePlanner,
    OracleDebugPlanner,
    RuleBasedPlanner,
)


MEMORY_PLANNERS = {
    "rule_based_no_memory": "no_memory",
    "short_memory": "short_memory",
    "object_memory": "object_memory",
}


def build_parser() -> argparse.ArgumentParser:
    """Build episode command-line arguments."""

    parser = argparse.ArgumentParser(description="Run one embodied-agent episode.")
    parser.add_argument("--task", required=True, help="task name from configs/tasks.yaml")
    parser.add_argument("--scene", help="scene name; defaults by environment mode")
    parser.add_argument(
        "--planner",
        default="rule_based",
        choices=("rule_based", *MEMORY_PLANNERS, "oracle_debug"),
        help="planner implementation",
    )
    parser.add_argument("--mock", action="store_true", help="use the deterministic mock kitchen")
    parser.add_argument(
        "--partial-observability",
        action="store_true",
        help="expose only the current mock region/view to the planner",
    )
    parser.add_argument("--seed", type=int, default=0, help="deterministic partial mock layout seed")
    parser.add_argument("--max-steps", type=int, help="override the configured positive step limit")
    parser.add_argument("--output-dir", help="explicit episode output directory")
    parser.add_argument("--tasks-config", help="optional alternative tasks YAML file")
    parser.add_argument(
        "--stale-intervention",
        action="store_true",
        help="relocate hidden Apple after Knife pickup using the Phase 3 protocol",
    )
    parser.add_argument(
        "--short-term-capacity",
        type=int,
        default=2,
        help="short-memory transition capacity; Phase 3 pilot freezes this at 2",
    )
    return parser


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _visible_ids(observation: Any) -> set[str]:
    return {obj["objectId"] for obj in parse_objects(observation) if obj["visible"]}


def _summary_template(
    args: argparse.Namespace,
    scene: str,
    output_dir: Path,
    *,
    max_steps: int,
) -> dict[str, Any]:
    memory_variant = MEMORY_PLANNERS.get(args.planner)
    condition = "t1_stale" if args.stale_intervention else (
        "t2_stable" if args.task == "po_find_book_after_distraction" else "t1_stable"
    )
    return {
        "task": args.task,
        "condition": condition,
        "scene": scene,
        "planner": args.planner,
        "memory_variant": memory_variant,
        "short_term_capacity": args.short_term_capacity if memory_variant == "short_memory" else None,
        "mode": "mock_partial" if args.partial_observability else ("mock" if args.mock else "ai2thor"),
        "partial_observability": args.partial_observability,
        "layout_seed": args.seed if args.partial_observability else None,
        "max_steps": max_steps,
        "privileged_planner": args.planner == "oracle_debug",
        "success": False,
        "steps": 0,
        "invalid_action_count": 0,
        "invalid_action_rate": 0.0,
        "llm_calls": 0,
        "search_move_count": 0,
        "repeated_region_visit_count": 0,
        "memory_update_count": 0,
        "object_record_update_count": 0,
        "memory_retrieval_count": 0,
        "memory_hint_count": 0,
        "memory_guided_action_count": 0,
        "last_seen_hit_count": 0,
        "stale_memory_miss_count": 0,
        "stale_record_recovery_count": 0,
        "recovery_search_move_count": 0,
        "intervention_count": 0,
        "intervention_id": None,
        "intervention_destination": None,
        "information_leak_audit_passed": None,
        "ordered_subgoal_passed": None,
        "protocol_violations": [],
        "average_planning_latency_seconds": 0.0,
        "total_episode_latency_seconds": 0.0,
        "failure_reason": "",
        "output_dir": str(output_dir),
        "started_at": _utc_now(),
    }


def _memory_provenance_is_valid(
    snapshot: Mapping[str, Any], visible_history: Mapping[str, set[str]]
) -> bool:
    kind = snapshot.get("kind")
    if kind == "none":
        return snapshot.get("records") == {}
    if kind == "short_term":
        records = snapshot.get("short_term", {}).get("records", [])
        return all(record.get("observation_id") in visible_history for record in records)
    if kind == "object":
        records = snapshot.get("objects", {})
        return all(
            record.get("source_observation_id") in visible_history
            and object_id in visible_history.get(str(record.get("source_observation_id")), set())
            for object_id, record in records.items()
        )
    return False


def _validate_args(args: argparse.Namespace) -> str | None:
    if args.max_steps is not None and args.max_steps <= 0:
        return "--max-steps must be a positive integer"
    if args.short_term_capacity <= 0:
        return "--short-term-capacity must be a positive integer"
    if args.partial_observability and not args.mock:
        return "--partial-observability currently requires --mock"
    if args.planner in {*MEMORY_PLANNERS, "oracle_debug"} and not args.partial_observability:
        return f"--planner {args.planner} requires --mock --partial-observability"
    if args.stale_intervention and (
        not args.mock
        or not args.partial_observability
        or args.task != "po_slice_apple_put_plate"
    ):
        return "--stale-intervention requires the partial mock po_slice_apple_put_plate task"
    return None


def main(argv: list[str] | None = None) -> int:
    """Execute an episode and return zero only when its state goal succeeds."""

    args = build_parser().parse_args(argv)
    validation_error = _validate_args(args)
    if validation_error:
        print(validation_error, file=sys.stderr)
        return 2

    try:
        task = load_task(args.task, args.tasks_config)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as exc:
        print(f"Task configuration error: {exc}", file=sys.stderr)
        return 2

    max_steps = args.max_steps or (18 if args.stale_intervention else task.max_steps)
    scene = args.scene or (MockEnv.DEFAULT_SCENE if args.mock else "FloorPlan1")
    mode = "mock_partial" if args.partial_observability else ("mock" if args.mock else "ai2thor")
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else create_episode_dir(task_name=task.task_name, planner_name=args.planner, mode=mode)
    )
    logger = EpisodeLogger(output_dir)
    summary = _summary_template(args, scene, output_dir, max_steps=max_steps)

    env = (
        MockEnv(partial_observability=args.partial_observability, layout_seed=args.seed)
        if args.mock
        else ThorEnv()
    )
    if args.planner == "rule_based":
        planner: Any = RuleBasedPlanner()
    elif args.planner == "oracle_debug":
        planner = OracleDebugPlanner()
    else:
        planner = MemoryAwarePlanner()
    memory_variant = MEMORY_PLANNERS.get(args.planner, "no_memory")
    memory_provider = build_memory_provider(
        memory_variant, short_term_capacity=args.short_term_capacity
    )
    progress = TaskProgressTracker(task)
    action_log = ActionLog()
    action_space = ActionSpace()
    executor = ActionExecutor(action_space)
    current_observation: Any | None = None
    planning_latencies: list[float] = []
    invalid_action_count = 0
    search_move_count = 0
    repeated_region_visit_count = 0
    memory_update_count = 0
    object_record_update_count = 0
    memory_retrieval_count = 0
    memory_hint_count = 0
    memory_guided_action_count = 0
    last_seen_hit_count = 0
    stale_memory_miss_count = 0
    stale_record_recovery_count = 0
    recovery_search_move_count = 0
    pending_stale_recovery: set[str] = set()
    interventions: list[dict[str, Any]] = []
    visited_regions: set[str] = set()
    visible_history: dict[str, set[str]] = {}
    planner_input_audit = True
    episode_start = perf_counter()
    unmet_conditions: tuple[str, ...] = ()
    intervention_destination: str | None = None
    stale_intervention_armed = False

    try:
        env.reset(scene)
        current_observation = env.get_observation()
        evaluator_state = env.get_evaluator_state()
        initial_region = str(current_observation.get("agent", {}).get("region", ""))
        if initial_region:
            visited_regions.add(initial_region)
        visible_history["observation:0"] = _visible_ids(current_observation)
        if args.planner in MEMORY_PLANNERS:
            updated = memory_provider.observe(
                step=0,
                observation=current_observation,
                action={"action": "Reset"},
                success=True,
                error="",
                observation_id="observation:0",
            )
            memory_update_count += memory_variant != "no_memory"
            object_record_update_count += len(updated)
        if args.stale_intervention:
            knife = next(
                obj for obj in parse_objects(evaluator_state) if obj["objectType"] == "Knife"
            )
            intervention_destination = str(knife["region"])

        availability = check_object_availability(task, evaluator_state)
        if not availability.available:
            missing = ", ".join(availability.missing_object_types)
            summary["failure_reason"] = f"missing_required_objects: {missing}"
        else:
            success_result = evaluate_task_success(task, evaluator_state)
            unmet_conditions = success_result.unmet_conditions
            summary["success"] = success_result.success

            for step_number in range(1, max_steps + 1):
                if summary["success"]:
                    break

                observation_before_action = deepcopy(current_observation)
                observation_id = f"observation:{step_number}"
                planner_received_objects = parse_objects(observation_before_action)
                planner_received_ids = {obj["objectId"] for obj in planner_received_objects}
                memory_before = memory_provider.snapshot()
                progress_before = progress.snapshot()
                planning_start = perf_counter()
                if args.planner == "rule_based":
                    action = planner.plan(task, current_observation, memory=None, action_space=action_space)
                    planner_trace = {"decision_source": "legacy_rule", "retrieval_attempted": False, "memory_hint": None}
                elif args.planner == "oracle_debug":
                    action = planner.plan(
                        task,
                        current_observation,
                        memory=None,
                        action_space=action_space,
                        evaluator_state=evaluator_state,
                    )
                    planner_trace = {"decision_source": "oracle", "retrieval_attempted": False, "memory_hint": None}
                else:
                    action = planner.plan(
                        task,
                        current_observation,
                        memory=memory_provider,
                        action_space=action_space,
                        evaluator_state=None,
                        task_progress=progress,
                    )
                    planner_trace = planner.trace_snapshot()
                planning_latency = perf_counter() - planning_start
                planning_latencies.append(planning_latency)

                if action is None:
                    summary["failure_reason"] = "planner_returned_no_action"
                    break
                if planner_trace.get("retrieval_attempted"):
                    memory_retrieval_count += 1
                hint_payload = planner_trace.get("memory_hint")
                if hint_payload:
                    memory_hint_count += 1
                if planner_trace.get("decision_source") == "memory_hint":
                    memory_guided_action_count += 1
                if action.get("objectId") and action["objectId"] not in planner_received_ids:
                    planner_input_audit = False
                if action.get("action") == "MoveToRegion":
                    search_move_count += 1
                    destination = str(action.get("region", ""))
                    if destination in visited_regions:
                        repeated_region_visit_count += 1
                    if pending_stale_recovery and planner_trace.get("decision_source") == "systematic_fallback":
                        recovery_search_move_count += 1

                action_start = perf_counter()
                execution = executor.execute(env, action)
                action_latency = perf_counter() - action_start
                intervention_record: dict[str, Any] | None = None
                if execution.event is not None:
                    current_observation = env.get_observation()

                if (
                    args.stale_intervention
                    and not interventions
                    and execution.success
                    and action.get("action") == "PickupObject"
                    and action.get("objectId") == "Knife|1"
                    and "Apple|1" not in _visible_ids(current_observation)
                ):
                    stale_intervention_armed = True

                if (
                    args.stale_intervention
                    and stale_intervention_armed
                    and not interventions
                    and execution.success
                    and action.get("action") == "MoveToRegion"
                    and str(current_observation.get("agent", {}).get("region", ""))
                    != intervention_destination
                ):
                    intervention_record = env.relocate_object_for_experiment(
                        "Apple|1", str(intervention_destination)
                    )
                    intervention_record.update(
                        {
                            "intervention_id": "phase3_v2_stale_apple_after_knife_departure",
                            "trigger_step": step_number,
                            "trigger": "first_departure_from_knife_region_after_successful_pickup",
                        }
                    )
                    interventions.append(deepcopy(intervention_record))
                    stale_intervention_armed = False
                    current_observation = env.get_observation()

                evaluator_state = env.get_evaluator_state()
                current_region = str(current_observation.get("agent", {}).get("region", ""))
                if action.get("action") == "MoveToRegion" and current_region:
                    visited_regions.add(current_region)
                visible_history[observation_id] = _visible_ids(current_observation)
                if execution.invalid_action:
                    invalid_action_count += 1

                progress.observe_action(
                    step=step_number,
                    action=action,
                    success=execution.success,
                    observation_after=current_observation,
                )

                if (
                    execution.success
                    and action.get("action") == "MoveToRegion"
                    and planner_trace.get("decision_source") == "memory_hint"
                    and isinstance(hint_payload, Mapping)
                ):
                    hint = MemoryHint(**dict(hint_payload))
                    visible_types = {obj["objectType"] for obj in parse_objects(current_observation)}
                    if hint.object_type in visible_types:
                        last_seen_hit_count += 1
                    elif memory_provider.mark_expected_region_miss(
                        hint, current_observation, step=step_number
                    ):
                        stale_memory_miss_count += 1
                        pending_stale_recovery.add(hint.object_id)

                updated_ids: list[str] = []
                if args.planner in MEMORY_PLANNERS:
                    updated_ids = memory_provider.observe(
                        step=step_number,
                        observation=current_observation,
                        action=action,
                        success=execution.success,
                        error=execution.error_message,
                        observation_id=observation_id,
                    )
                    memory_update_count += memory_variant != "no_memory"
                    object_record_update_count += len(updated_ids)
                recovered = pending_stale_recovery.intersection(updated_ids)
                if recovered:
                    stale_record_recovery_count += len(recovered)
                    pending_stale_recovery.difference_update(recovered)

                action_log.add(
                    step=step_number,
                    action=action,
                    success=execution.success,
                    error=execution.error_message,
                    latency_seconds=action_latency,
                )
                memory_after = memory_provider.snapshot()
                success_result = evaluate_task_success(task, evaluator_state)
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
                        "agent_observation_before_action": observation_before_action,
                        "agent_observation_after_action": current_observation,
                        "visible_objects": parse_objects(current_observation),
                        "planner_received_object_ids": sorted(planner_received_ids),
                        "privileged_planner": args.planner == "oracle_debug",
                        "planner_trace": planner_trace,
                        "memory_snapshot_before_retrieval": memory_before,
                        "retrieved_memory_records": [hint_payload] if hint_payload else [],
                        "memory_snapshot_after_action_feedback": memory_after,
                        "memory_updated_object_ids": updated_ids,
                        "action_log_entry": action_log.snapshot()[-1],
                        "task_progress_before": progress_before,
                        "task_progress_after": progress.snapshot(),
                        "environment_intervention": intervention_record,
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

    final_memory = memory_provider.snapshot()
    progress_summary = progress.snapshot()
    summary.update(
        {
            "invalid_action_count": invalid_action_count,
            "search_move_count": search_move_count,
            "repeated_region_visit_count": repeated_region_visit_count,
            "memory_update_count": memory_update_count,
            "object_record_update_count": object_record_update_count,
            "memory_retrieval_count": memory_retrieval_count,
            "memory_hint_count": memory_hint_count,
            "memory_guided_action_count": memory_guided_action_count,
            "last_seen_hit_count": last_seen_hit_count,
            "stale_memory_miss_count": stale_memory_miss_count,
            "stale_record_recovery_count": stale_record_recovery_count,
            "recovery_search_move_count": recovery_search_move_count,
            "intervention_count": len(interventions),
            "intervention_id": interventions[0]["intervention_id"] if interventions else None,
            "intervention_destination": intervention_destination if interventions else None,
            "information_leak_audit_passed": (
                None
                if args.planner == "oracle_debug"
                else planner_input_audit
                and _memory_provenance_is_valid(final_memory, visible_history)
            ),
            "ordered_subgoal_passed": progress_summary["ordered_subgoal_passed"],
            "protocol_violations": progress_summary["protocol_violations"],
            "final_memory_snapshot": final_memory,
        }
    )
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

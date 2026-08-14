"""Formal/debug decision-engine parity helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def decision_engine_signature(record: Mapping[str, Any]) -> dict[str, Any]:
    """Drop timestamps, paths, and presentation timing from one trace step."""

    planner_input = record.get("planner_input", {})
    decision = record.get("planner_decision", {})
    feedback = record.get("environment_feedback", {})
    request = planner_input.get("request", {}) if isinstance(planner_input, Mapping) else {}
    return {
        "step": record.get("step"),
        "planner_request": request,
        "planner_input_audit": (
            planner_input.get("audit") if isinstance(planner_input, Mapping) else None
        ),
        "decision": {
            key: decision.get(key)
            for key in (
                "action",
                "target_object_type",
                "memory_guided",
                "memory_record_ids",
                "reason_code",
                "rationale",
                "planner_name",
                "validation_passed",
                "validation_errors",
            )
        }
        if isinstance(decision, Mapping)
        else decision,
        "feedback": {
            key: feedback.get(key)
            for key in (
                "action_success",
                "invalid_action",
                "error_message",
                "post_action_observation",
                "memory_before",
                "memory_update",
                "memory_updated_record_ids",
                "memory_after",
                "task_progress",
                "task_success",
            )
        }
        if isinstance(feedback, Mapping)
        else feedback,
    }


def load_decision_signatures(path: str | Path) -> list[dict[str, Any]]:
    """Load canonical signatures from an episode JSONL file."""

    trace_path = Path(path).expanduser().resolve()
    signatures: list[dict[str, Any]] = []
    with trace_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValueError(f"trace line {line_number} is not a JSON object")
            signatures.append(decision_engine_signature(value))
    return signatures


def compare_trace_parity(
    formal_episode_path: str | Path, debug_episode_path: str | Path
) -> dict[str, Any]:
    """Compare semantics while deliberately ignoring presentation-only fields."""

    formal = load_decision_signatures(formal_episode_path)
    debug = load_decision_signatures(debug_episode_path)
    mismatches: list[dict[str, Any]] = []
    for index in range(max(len(formal), len(debug))):
        left = formal[index] if index < len(formal) else None
        right = debug[index] if index < len(debug) else None
        if left != right:
            mismatches.append({"step_index": index, "formal": left, "debug": right})
    return {
        "passed": not mismatches,
        "formal_step_count": len(formal),
        "debug_step_count": len(debug),
        "mismatches": mismatches,
    }

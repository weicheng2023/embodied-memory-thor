"""Evaluate task success exclusively from environment object state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from embodied_memory_thor.env.object_parser import parse_objects
from embodied_memory_thor.evaluation.task_loader import TaskDefinition


@dataclass(frozen=True)
class SuccessResult:
    """State-based success verdict with unmet-condition explanations."""

    success: bool
    unmet_conditions: tuple[str, ...]


def evaluate_task_success(task: TaskDefinition, event_or_metadata: Any) -> SuccessResult:
    """Require every configured goal condition to hold in object metadata."""

    objects = parse_objects(event_or_metadata)
    unmet: list[str] = []
    for condition in task.goal_conditions:
        satisfied, explanation = _evaluate_condition(condition, objects)
        if not satisfied:
            unmet.append(explanation)
    return SuccessResult(success=not unmet, unmet_conditions=tuple(unmet))


def _evaluate_condition(
    condition: Mapping[str, Any],
    objects: list[dict[str, Any]],
) -> tuple[bool, str]:
    condition_type = condition.get("type")
    if condition_type == "object_in_receptacle":
        return _object_in_receptacle(condition, objects)
    if condition_type == "object_state":
        return _object_state(condition, objects)
    return False, f"unsupported goal condition type: {condition_type!r}"


def _objects_of_type(objects: list[dict[str, Any]], object_type: str) -> list[dict[str, Any]]:
    expected = object_type.casefold()
    return [obj for obj in objects if obj["objectType"].casefold() == expected]


def _parent_type(parent_id: str, objects_by_id: dict[str, dict[str, Any]]) -> str:
    parent = objects_by_id.get(parent_id)
    if parent is not None:
        return parent["objectType"]
    return parent_id.split("|", 1)[0]


def _object_in_receptacle(
    condition: Mapping[str, Any],
    objects: list[dict[str, Any]],
) -> tuple[bool, str]:
    object_type = str(condition.get("object_type", ""))
    receptacle_type = str(condition.get("receptacle_type", ""))
    if not object_type or not receptacle_type:
        return False, "object_in_receptacle requires object_type and receptacle_type"

    objects_by_id = {obj["objectId"]: obj for obj in objects if obj["objectId"]}
    candidates = _objects_of_type(objects, object_type)
    for candidate in candidates:
        if any(
            _parent_type(parent_id, objects_by_id).casefold() == receptacle_type.casefold()
            for parent_id in candidate["parentReceptacles"]
        ):
            return True, ""
    return False, f"no {object_type} is in a {receptacle_type}"


def _object_state(
    condition: Mapping[str, Any],
    objects: list[dict[str, Any]],
) -> tuple[bool, str]:
    object_type = str(condition.get("object_type", ""))
    field = str(condition.get("field", ""))
    expected = condition.get("equals")
    if not object_type or not field:
        return False, "object_state requires object_type and field"

    candidates = _objects_of_type(objects, object_type)
    if any(candidate.get(field) == expected for candidate in candidates):
        return True, ""
    return False, f"no {object_type} has {field}={expected!r}"

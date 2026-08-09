"""Required-object checks that prevent impossible tasks from starting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from embodied_memory_thor.env.object_parser import parse_objects
from embodied_memory_thor.evaluation.task_loader import TaskDefinition


@dataclass(frozen=True)
class AvailabilityResult:
    """Availability verdict and the object IDs supporting it."""

    available: bool
    missing_object_types: tuple[str, ...]
    matching_object_ids: dict[str, tuple[str, ...]]


def check_object_availability(
    task: TaskDefinition,
    event_or_metadata: Any,
) -> AvailabilityResult:
    """Check all task requirements against scene metadata by object type."""

    objects = parse_objects(event_or_metadata)
    by_type: dict[str, list[str]] = {}
    for obj in objects:
        by_type.setdefault(obj["objectType"].casefold(), []).append(obj["objectId"])

    matches: dict[str, tuple[str, ...]] = {}
    missing: list[str] = []
    for required_type in task.required_objects:
        object_ids = tuple(by_type.get(required_type.casefold(), []))
        matches[required_type] = object_ids
        if not object_ids:
            missing.append(required_type)

    return AvailabilityResult(
        available=not missing,
        missing_object_types=tuple(missing),
        matching_object_ids=matches,
    )

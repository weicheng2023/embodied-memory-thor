"""Deterministic rule-based retrieval over structured object memory."""

from __future__ import annotations

import re

from embodied_memory_thor.memory.object_memory import ObjectMemory, ObjectMemoryRecord


def retrieve_relevant_objects(
    task_instruction: str,
    memory: ObjectMemory,
    *,
    required_object_types: tuple[str, ...] = (),
    include_stale: bool = True,
) -> list[ObjectMemoryRecord]:
    """Retrieve object types named by task text or explicit requirements."""

    tokens = set(re.findall(r"[a-z0-9]+", task_instruction.casefold()))
    candidates = set(required_object_types)
    for record in memory.snapshot().values():
        object_type = str(record["object_type"])
        if object_type.casefold() in tokens:
            candidates.add(object_type)

    results: list[ObjectMemoryRecord] = []
    for object_type in sorted(candidates, key=str.casefold):
        results.extend(memory.retrieve(object_type, include_stale=include_stale))
    return sorted(results, key=lambda item: (-item.last_seen_step, item.object_id))

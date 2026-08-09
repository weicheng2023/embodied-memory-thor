"""Observation-derived ordered-subgoal tracking shared by all variants."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from embodied_memory_thor.env.object_parser import parse_objects
from embodied_memory_thor.evaluation.task_loader import TaskDefinition


class TaskProgressTracker:
    """Track only prescribed milestones, never locations or observation history."""

    def __init__(self, task: TaskDefinition) -> None:
        self.task_name = task.task_name
        self._lamp_toggled_step: int | None = None
        self._book_picked_step: int | None = None
        self._protocol_violations: list[str] = []

    @property
    def stage(self) -> str:
        """Return the current ordered task stage."""

        if self.task_name != "po_find_book_after_distraction":
            return "state_driven"
        if self._lamp_toggled_step is None:
            return "toggle_desklamp"
        if self._book_picked_step is None:
            return "pickup_book"
        return "complete"

    def observe_action(
        self,
        *,
        step: int,
        action: Mapping[str, Any],
        success: bool,
        observation_after: Any,
    ) -> None:
        """Record successful ordered interactions using agent-visible metadata."""

        if self.task_name != "po_find_book_after_distraction" or not success:
            return
        object_id = str(action.get("objectId", ""))
        by_id = {obj["objectId"]: obj for obj in parse_objects(observation_after)}
        target = by_id.get(object_id)
        target_type = str(target.get("objectType", "")) if target else object_id.split("|", 1)[0]
        action_name = str(action.get("action", ""))

        if action_name == "ToggleObjectOn" and target_type == "DeskLamp":
            if self._lamp_toggled_step is None:
                self._lamp_toggled_step = int(step)
        if action_name == "PickupObject" and target_type == "Book":
            if self._lamp_toggled_step is None:
                self._protocol_violations.append(f"book_picked_before_lamp_at_step:{step}")
            if self._book_picked_step is None:
                self._book_picked_step = int(step)

    def snapshot(self) -> dict[str, Any]:
        """Return the small auditable milestone state."""

        ordered = (
            self._lamp_toggled_step is not None
            and self._book_picked_step is not None
            and self._lamp_toggled_step < self._book_picked_step
            and not self._protocol_violations
        )
        return deepcopy(
            {
                "task_name": self.task_name,
                "stage": self.stage,
                "lamp_toggled_step": self._lamp_toggled_step,
                "book_picked_step": self._book_picked_step,
                "ordered_subgoal_passed": ordered if self._book_picked_step is not None else None,
                "protocol_violations": list(self._protocol_violations),
            }
        )

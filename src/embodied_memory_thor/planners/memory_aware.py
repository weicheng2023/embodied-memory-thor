"""One shared task/search policy parameterized by a memory hint provider."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from embodied_memory_thor.env.object_parser import metadata_from_event, parse_objects
from embodied_memory_thor.evaluation.task_loader import TaskDefinition
from embodied_memory_thor.evaluation.task_progress import TaskProgressTracker
from embodied_memory_thor.memory.providers import MemoryHint, MemoryProvider, NoMemoryProvider


class MemoryAwarePlanner:
    """Apply identical task rules and fallback search for all memory variants."""

    REGION_ORDER = ("Kitchen", "DiningArea", "SinkArea")

    def __init__(self) -> None:
        self.last_trace: dict[str, Any] = {}

    def plan(
        self,
        task: TaskDefinition,
        observation: Any,
        memory: MemoryProvider | None = None,
        action_space: Any | None = None,
        evaluator_state: Mapping[str, Any] | None = None,
        task_progress: TaskProgressTracker | None = None,
    ) -> dict[str, Any] | None:
        """Return one action without reading evaluator state."""

        del action_space, evaluator_state
        provider = memory or NoMemoryProvider()
        metadata = metadata_from_event(observation)
        objects = parse_objects(metadata)
        by_type = {obj["objectType"]: obj for obj in objects}
        held = next((obj for obj in objects if obj["isPickedUp"]), None)
        region = str(metadata.get("agent", {}).get("region", ""))
        self.last_trace = {
            "task": task.task_name,
            "target_object_type": None,
            "decision_source": "task_policy",
            "memory_hint": None,
            "retrieval_attempted": False,
        }

        if task.task_name == "po_slice_apple_put_plate":
            return self._plan_slice(by_type, held, region, provider)
        if task.task_name == "po_find_book_after_distraction":
            progress = task_progress or TaskProgressTracker(task)
            return self._plan_book(by_type, held, region, provider, progress)
        return None

    def trace_snapshot(self) -> dict[str, Any]:
        """Return only the current decision trace, not trajectory history."""

        return deepcopy(self.last_trace)

    def _plan_slice(
        self,
        by_type: dict[str, dict[str, Any]],
        held: dict[str, Any] | None,
        region: str,
        memory: MemoryProvider,
    ) -> dict[str, Any]:
        apple = by_type.get("Apple")
        knife = by_type.get("Knife")
        plate = by_type.get("Plate")

        if apple is not None and not apple["isSliced"]:
            if held is not None and held["objectType"] == "Knife":
                return self._visible_action("Apple", "SliceObject", apple["objectId"])
            if held is not None:
                return self._policy_action({"action": "DropHandObject"})
            if knife is not None:
                return self._visible_action("Knife", "PickupObject", knife["objectId"])
            return self._seek("Knife", region, memory)

        if apple is None:
            if held is None and knife is not None:
                return self._visible_action("Knife", "PickupObject", knife["objectId"])
            target = "Apple" if held is not None and held["objectType"] == "Knife" else "Knife"
            return self._seek(target, region, memory)

        if held is not None and held["objectType"] == "Knife":
            return self._policy_action({"action": "DropHandObject"})
        if held is None:
            return self._visible_action("Apple", "PickupObject", apple["objectId"])
        if held["objectType"] == "Apple" and plate is not None:
            return self._visible_action("Plate", "PutObject", plate["objectId"])
        if held["objectType"] == "Apple":
            return self._seek("Plate", region, memory)
        return self._policy_action({"action": "DropHandObject"})

    def _plan_book(
        self,
        by_type: dict[str, dict[str, Any]],
        held: dict[str, Any] | None,
        region: str,
        memory: MemoryProvider,
        progress: TaskProgressTracker,
    ) -> dict[str, Any]:
        if progress.stage == "toggle_desklamp":
            lamp = by_type.get("DeskLamp")
            if lamp is not None:
                return self._visible_action("DeskLamp", "ToggleObjectOn", lamp["objectId"])
            return self._seek("DeskLamp", region, memory)

        if progress.stage == "pickup_book":
            book = by_type.get("Book")
            if held is not None and held["objectType"] != "Book":
                return self._policy_action({"action": "DropHandObject"})
            if book is not None:
                return self._visible_action("Book", "PickupObject", book["objectId"])
            return self._seek("Book", region, memory)

        return self._policy_action({"action": "Pass"})

    def _visible_action(self, target: str, action: str, object_id: str) -> dict[str, Any]:
        self.last_trace.update(
            {"target_object_type": target, "decision_source": "current_observation"}
        )
        return {"action": action, "objectId": object_id}

    def _policy_action(self, action: dict[str, Any]) -> dict[str, Any]:
        self.last_trace["decision_source"] = "task_policy"
        return action

    def _seek(
        self, target: str, current_region: str, memory: MemoryProvider
    ) -> dict[str, Any]:
        self.last_trace["target_object_type"] = target
        self.last_trace["retrieval_attempted"] = True
        hint = memory.hint(target)
        if hint is not None and hint.region != current_region:
            self.last_trace.update(
                {"decision_source": "memory_hint", "memory_hint": hint.snapshot()}
            )
            return {"action": "MoveToRegion", "region": hint.region}
        return self._fallback(current_region, ignored_hint=hint)

    def _fallback(
        self, current_region: str, *, ignored_hint: MemoryHint | None = None
    ) -> dict[str, str]:
        try:
            index = self.REGION_ORDER.index(current_region)
        except ValueError:
            index = -1
        self.last_trace.update(
            {
                "decision_source": "systematic_fallback",
                "memory_hint": ignored_hint.snapshot() if ignored_hint else None,
            }
        )
        return {
            "action": "MoveToRegion",
            "region": self.REGION_ORDER[(index + 1) % len(self.REGION_ORDER)],
        }

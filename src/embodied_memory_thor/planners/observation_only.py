"""Reactive no-memory search baseline for the partial mock harness."""

from __future__ import annotations

from typing import Any, Mapping

from embodied_memory_thor.env.object_parser import metadata_from_event, parse_objects
from embodied_memory_thor.evaluation.task_loader import TaskDefinition


class ObservationOnlyPlanner:
    """Plan from only the current local observation and inventory state.

    The planner has no retained search history. When a required object is not
    visible, it follows a fixed region cycle. This provides a reproducible
    no-memory baseline for later comparison with last-seen object retrieval.
    """

    name = "rule_based_no_memory"
    REGION_ORDER = ("Kitchen", "DiningArea", "SinkArea")

    def plan(
        self,
        task: TaskDefinition,
        observation: Any,
        memory: Any | None = None,
        action_space: Any | None = None,
        evaluator_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Return one action without consuming memory or evaluator state."""

        del memory, action_space, evaluator_state
        if task.task_name != "po_slice_apple_put_plate":
            return None

        metadata = metadata_from_event(observation)
        objects = parse_objects(metadata)
        by_type = {obj["objectType"]: obj for obj in objects}
        held = next((obj for obj in objects if obj["isPickedUp"]), None)
        region = str(metadata.get("agent", {}).get("region", ""))
        apple = by_type.get("Apple")
        knife = by_type.get("Knife")
        plate = by_type.get("Plate")

        if apple is not None and not apple["isSliced"]:
            if held is not None and held["objectType"] == "Knife":
                return {"action": "SliceObject", "objectId": apple["objectId"]}
            if held is not None:
                return {"action": "DropHandObject"}
            if knife is not None:
                return {"action": "PickupObject", "objectId": knife["objectId"]}
            return self._search(region)

        if apple is None:
            if held is None and knife is not None:
                return {"action": "PickupObject", "objectId": knife["objectId"]}
            return self._search(region)

        if held is not None and held["objectType"] == "Knife":
            return {"action": "DropHandObject"}
        if held is None:
            return {"action": "PickupObject", "objectId": apple["objectId"]}
        if held["objectType"] == "Apple" and plate is not None:
            return {"action": "PutObject", "objectId": plate["objectId"]}
        if held["objectType"] == "Apple":
            return self._search(region)
        return {"action": "DropHandObject"}

    def _search(self, current_region: str) -> dict[str, str]:
        try:
            index = self.REGION_ORDER.index(current_region)
        except ValueError:
            index = -1
        return {
            "action": "MoveToRegion",
            "region": self.REGION_ORDER[(index + 1) % len(self.REGION_ORDER)],
        }

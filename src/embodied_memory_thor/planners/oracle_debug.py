"""Privileged oracle used only to prove partial mock task solvability."""

from __future__ import annotations

from typing import Any, Mapping

from embodied_memory_thor.env.object_parser import parse_objects
from embodied_memory_thor.evaluation.task_loader import TaskDefinition


class OracleDebugPlanner:
    """Use evaluator state to move directly to hidden objects.

    This planner intentionally violates the agent information boundary and is
    labeled privileged in every run. It is a debugging upper bound, never an
    experimental memory baseline.
    """

    name = "oracle_debug"
    uses_privileged_state = True

    def plan(
        self,
        task: TaskDefinition,
        observation: Any,
        memory: Any | None = None,
        action_space: Any | None = None,
        evaluator_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Return a direct action using full state solely for smoke/debug use."""

        del memory, action_space
        if task.task_name != "po_slice_apple_put_plate" or evaluator_state is None:
            return None

        observed = parse_objects(observation)
        full_objects = parse_objects(evaluator_state)
        visible_by_type = {obj["objectType"]: obj for obj in observed}
        full_by_type = {obj["objectType"]: obj for obj in full_objects}
        held = next((obj for obj in observed if obj["isPickedUp"]), None)
        apple = full_by_type.get("Apple")
        knife = full_by_type.get("Knife")
        plate = full_by_type.get("Plate")
        if apple is None or knife is None or plate is None:
            return None

        if not apple["isSliced"]:
            if held is not None and held["objectType"] == "Knife":
                if "Apple" in visible_by_type:
                    return {"action": "SliceObject", "objectId": apple["objectId"]}
                return {"action": "MoveToRegion", "region": apple["region"]}
            if held is not None:
                return {"action": "DropHandObject"}
            if "Knife" in visible_by_type:
                return {"action": "PickupObject", "objectId": knife["objectId"]}
            return {"action": "MoveToRegion", "region": knife["region"]}

        if held is not None and held["objectType"] == "Knife":
            return {"action": "DropHandObject"}
        if held is None:
            if "Apple" in visible_by_type:
                return {"action": "PickupObject", "objectId": apple["objectId"]}
            return {"action": "MoveToRegion", "region": apple["region"]}
        if held["objectType"] == "Apple":
            if "Plate" in visible_by_type:
                return {"action": "PutObject", "objectId": plate["objectId"]}
            return {"action": "MoveToRegion", "region": plate["region"]}
        return {"action": "DropHandObject"}

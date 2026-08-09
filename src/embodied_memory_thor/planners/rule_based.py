"""Transparent state-machine baseline for the configured kitchen tasks."""

from __future__ import annotations

from typing import Any

from embodied_memory_thor.env.object_parser import parse_objects
from embodied_memory_thor.evaluation.task_loader import TaskDefinition


class RuleBasedPlanner:
    """Choose the next action from current metadata using explicit rules."""

    name = "rule_based"

    def plan(
        self,
        task: TaskDefinition,
        observation: Any,
        memory: Any | None = None,
        action_space: Any | None = None,
    ) -> dict[str, Any] | None:
        """Return one action, or ``None`` when no rule applies."""

        del memory, action_space
        objects = parse_objects(observation)
        by_type = {obj["objectType"]: obj for obj in objects}

        if task.task_name == "put_apple_on_countertop":
            return self._place_apple(by_type, "CounterTop")
        if task.task_name == "put_apple_on_plate":
            return self._place_apple(by_type, "Plate")
        if task.task_name == "wash_apple_put_countertop":
            return self._wash_and_place(by_type)
        if task.task_name == "slice_apple_put_plate":
            return self._slice_and_place(by_type)
        return None

    @staticmethod
    def _held_object(by_type: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        return next((obj for obj in by_type.values() if obj["isPickedUp"]), None)

    @staticmethod
    def _is_in(obj: dict[str, Any], receptacle_type: str) -> bool:
        return any(
            parent_id.split("|", 1)[0].casefold() == receptacle_type.casefold()
            for parent_id in obj["parentReceptacles"]
        )

    def _place_apple(
        self,
        by_type: dict[str, dict[str, Any]],
        receptacle_type: str,
    ) -> dict[str, Any] | None:
        apple = by_type.get("Apple")
        receptacle = by_type.get(receptacle_type)
        if apple is None or receptacle is None or self._is_in(apple, receptacle_type):
            return None

        held = self._held_object(by_type)
        if held is None:
            return {"action": "PickupObject", "objectId": apple["objectId"]}
        if held["objectType"] == "Apple":
            return {"action": "PutObject", "objectId": receptacle["objectId"]}
        return {"action": "DropHandObject"}

    def _wash_and_place(self, by_type: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        apple = by_type.get("Apple")
        sink = by_type.get("SinkBasin")
        faucet = by_type.get("Faucet")
        countertop = by_type.get("CounterTop")
        if None in (apple, sink, faucet, countertop):
            return None

        held = self._held_object(by_type)
        if apple["isDirty"]:
            if self._is_in(apple, "SinkBasin"):
                if not faucet["isToggled"]:
                    return {"action": "ToggleObjectOn", "objectId": faucet["objectId"]}
                return {"action": "CleanObject", "objectId": apple["objectId"]}
            if held is None:
                return {"action": "PickupObject", "objectId": apple["objectId"]}
            if held["objectType"] == "Apple":
                return {"action": "PutObject", "objectId": sink["objectId"]}
            return {"action": "DropHandObject"}

        if self._is_in(apple, "CounterTop"):
            return None
        if held is None:
            return {"action": "PickupObject", "objectId": apple["objectId"]}
        if held["objectType"] == "Apple":
            return {"action": "PutObject", "objectId": countertop["objectId"]}
        return {"action": "DropHandObject"}

    def _slice_and_place(self, by_type: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        apple = by_type.get("Apple")
        knife = by_type.get("Knife")
        plate = by_type.get("Plate")
        countertop = by_type.get("CounterTop")
        if None in (apple, knife, plate, countertop):
            return None

        held = self._held_object(by_type)
        if not apple["isSliced"]:
            if held is None:
                return {"action": "PickupObject", "objectId": knife["objectId"]}
            if held["objectType"] == "Knife":
                return {"action": "SliceObject", "objectId": apple["objectId"]}
            return {"action": "DropHandObject"}

        if held is not None and held["objectType"] == "Knife":
            return {"action": "PutObject", "objectId": countertop["objectId"]}
        if self._is_in(apple, "Plate"):
            return None
        if held is None:
            return {"action": "PickupObject", "objectId": apple["objectId"]}
        if held["objectType"] == "Apple":
            return {"action": "PutObject", "objectId": plate["objectId"]}
        return {"action": "DropHandObject"}

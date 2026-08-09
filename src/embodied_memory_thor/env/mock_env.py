"""Deterministic kitchen mock with AI2-THOR-like metadata and actions."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from embodied_memory_thor.env.base import EmbodiedEnv


@dataclass(frozen=True)
class MockEvent:
    """Small event object exposing the metadata attribute used by AI2-THOR."""

    metadata: dict[str, Any]
    frame: None = None


def _position(x: float, y: float, z: float) -> dict[str, float]:
    return {"x": x, "y": y, "z": z}


def _object(
    object_type: str,
    object_id: str,
    position: dict[str, float],
    *,
    pickupable: bool = False,
    receptacle: bool = False,
    parent_receptacles: list[str] | None = None,
    openable: bool = False,
    toggleable: bool = False,
    sliceable: bool = False,
    dirtyable: bool = False,
) -> dict[str, Any]:
    """Build one complete, mutable mock object record."""

    return {
        "objectType": object_type,
        "objectId": object_id,
        "name": object_id,
        "position": position,
        "visible": True,
        "pickupable": pickupable,
        "receptacle": receptacle,
        "parentReceptacles": list(parent_receptacles or []),
        "receptacleObjectIds": [],
        "openable": openable,
        "toggleable": toggleable,
        "sliceable": sliceable,
        "dirtyable": dirtyable,
        "isPickedUp": False,
        "isOpen": False,
        "isToggled": False,
        "isSliced": False,
        "isDirty": dirtyable,
    }


class MockEnv(EmbodiedEnv):
    """A deterministic in-memory kitchen used when Unity is unavailable.

    The mock intentionally models only a small action subset. Each action
    returns metadata with ``lastActionSuccess`` and ``errorMessage`` so later
    phases can share logging and evaluation code with the real adapter.
    """

    DEFAULT_SCENE = "MockKitchen"

    def __init__(self) -> None:
        self._scene_name = self.DEFAULT_SCENE
        self._objects: dict[str, dict[str, Any]] = {}
        self._agent: dict[str, Any] = {}
        self._held_object_id: str | None = None
        self._last_event: MockEvent | None = None
        self.reset(self.DEFAULT_SCENE)

    @property
    def last_event(self) -> MockEvent:
        """Return the most recent mock event."""

        if self._last_event is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("Mock environment has not been reset")
        return self._last_event

    def reset(self, scene: str = DEFAULT_SCENE) -> MockEvent:
        """Restore the deterministic kitchen scene."""

        self._scene_name = scene or self.DEFAULT_SCENE
        countertop = "CounterTop|1"
        self._objects = {
            countertop: _object("CounterTop", countertop, _position(0.0, 0.9, 1.5), receptacle=True),
            "Plate|1": _object(
                "Plate",
                "Plate|1",
                _position(0.25, 0.95, 1.5),
                pickupable=True,
                receptacle=True,
                parent_receptacles=[countertop],
            ),
            "Apple|1": _object(
                "Apple",
                "Apple|1",
                _position(-0.2, 0.95, 1.5),
                pickupable=True,
                sliceable=True,
                dirtyable=True,
                parent_receptacles=[countertop],
            ),
            "Knife|1": _object(
                "Knife",
                "Knife|1",
                _position(0.55, 0.95, 1.5),
                pickupable=True,
                parent_receptacles=[countertop],
            ),
            "SinkBasin|1": _object(
                "SinkBasin",
                "SinkBasin|1",
                _position(-1.0, 0.85, 1.2),
                receptacle=True,
            ),
            "Faucet|1": _object(
                "Faucet",
                "Faucet|1",
                _position(-1.0, 1.1, 1.1),
                toggleable=True,
            ),
            "Cabinet|1": _object(
                "Cabinet",
                "Cabinet|1",
                _position(1.2, 1.1, 1.3),
                receptacle=True,
                openable=True,
            ),
        }
        self._agent = {
            "position": _position(0.0, 0.9, 0.0),
            "rotation": _position(0.0, 0.0, 0.0),
            "cameraHorizon": 0.0,
            "isStanding": True,
        }
        self._held_object_id = None
        self._refresh_receptacle_contents()
        self._last_event = self._make_event("Reset", True, "")
        return self._last_event

    def step(self, action_dict: Mapping[str, Any]) -> MockEvent:
        """Execute a supported action and return the resulting mock event."""

        if not isinstance(action_dict, Mapping):
            return self._finish("Unknown", False, "action_dict must be a mapping")

        action = str(action_dict.get("action", "")).strip()
        if not action:
            return self._finish("Unknown", False, "missing required action name")

        handlers = {
            "Pass": self._pass,
            "PickupObject": self._pickup_object,
            "PutObject": self._put_object,
            "DropHandObject": self._drop_hand_object,
            "SliceObject": self._slice_object,
            "ToggleObjectOn": self._toggle_object,
            "ToggleObjectOff": self._toggle_object,
            "OpenObject": self._open_close_object,
            "CloseObject": self._open_close_object,
            "DirtyObject": self._dirty_clean_object,
            "CleanObject": self._dirty_clean_object,
            "MoveAhead": self._move_ahead,
            "RotateLeft": self._rotate,
            "RotateRight": self._rotate,
            "LookUp": self._look,
            "LookDown": self._look,
        }
        handler = handlers.get(action)
        if handler is None:
            return self._finish(action, False, f"unsupported mock action: {action}")

        success, error = handler(action_dict)
        return self._finish(action, success, error)

    def get_visible_objects(self) -> list[dict[str, Any]]:
        """Return defensive copies of currently visible objects."""

        return [deepcopy(obj) for obj in self._objects.values() if obj["visible"]]

    def get_all_objects(self) -> list[dict[str, Any]]:
        """Return defensive copies of every object in the mock scene."""

        return [deepcopy(obj) for obj in self._objects.values()]

    def get_agent_state(self) -> dict[str, Any]:
        """Return a defensive copy of the agent state."""

        return deepcopy(self._agent)

    def save_frame(self, path: str | Path) -> Path:
        """Explain that the state-only mock does not render RGB frames."""

        raise RuntimeError(f"MockEnv does not render frames; cannot save {Path(path)}")

    def _make_event(self, action: str, success: bool, error: str) -> MockEvent:
        inventory = []
        if self._held_object_id:
            inventory.append(deepcopy(self._objects[self._held_object_id]))
        metadata = {
            "sceneName": self._scene_name,
            "objects": self.get_all_objects(),
            "agent": self.get_agent_state(),
            "inventoryObjects": inventory,
            "lastAction": action,
            "lastActionSuccess": success,
            "errorMessage": error,
            "actionReturn": None,
        }
        return MockEvent(metadata=metadata)

    def _finish(self, action: str, success: bool, error: str) -> MockEvent:
        self._refresh_receptacle_contents()
        self._last_event = self._make_event(action, success, error)
        return self._last_event

    def _target(self, action_dict: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
        object_id = str(action_dict.get("objectId", "")).strip()
        if not object_id:
            return None, "missing objectId"
        target = self._objects.get(object_id)
        if target is None:
            return None, f"unknown objectId: {object_id}"
        return target, ""

    def _pass(self, _: Mapping[str, Any]) -> tuple[bool, str]:
        return True, ""

    def _pickup_object(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        target, error = self._target(action_dict)
        if target is None:
            return False, error
        if self._held_object_id:
            return False, f"already holding {self._held_object_id}"
        if not target["visible"]:
            return False, f"object is not visible: {target['objectId']}"
        if not target["pickupable"]:
            return False, f"object is not pickupable: {target['objectId']}"

        target["isPickedUp"] = True
        target["parentReceptacles"] = []
        self._held_object_id = target["objectId"]
        return True, ""

    def _put_object(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        receptacle, error = self._target(action_dict)
        if receptacle is None:
            return False, error
        if not self._held_object_id:
            return False, "agent is not holding an object"
        if not receptacle["receptacle"]:
            return False, f"target is not a receptacle: {receptacle['objectId']}"
        if receptacle["openable"] and not receptacle["isOpen"]:
            return False, f"receptacle is closed: {receptacle['objectId']}"

        held = self._objects[self._held_object_id]
        held["isPickedUp"] = False
        held["parentReceptacles"] = [receptacle["objectId"]]
        held["position"] = deepcopy(receptacle["position"])
        self._held_object_id = None
        return True, ""

    def _drop_hand_object(self, _: Mapping[str, Any]) -> tuple[bool, str]:
        if not self._held_object_id:
            return False, "agent is not holding an object"
        held = self._objects[self._held_object_id]
        held["isPickedUp"] = False
        held["parentReceptacles"] = []
        held["position"] = deepcopy(self._agent["position"])
        self._held_object_id = None
        return True, ""

    def _slice_object(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        target, error = self._target(action_dict)
        if target is None:
            return False, error
        if not target["sliceable"]:
            return False, f"object is not sliceable: {target['objectId']}"
        if not self._held_object_id or self._objects[self._held_object_id]["objectType"] != "Knife":
            return False, "a knife must be held to slice an object"
        target["isSliced"] = True
        return True, ""

    def _toggle_object(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        target, error = self._target(action_dict)
        if target is None:
            return False, error
        if not target["toggleable"]:
            return False, f"object is not toggleable: {target['objectId']}"
        target["isToggled"] = action_dict["action"] == "ToggleObjectOn"
        return True, ""

    def _open_close_object(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        target, error = self._target(action_dict)
        if target is None:
            return False, error
        if not target["openable"]:
            return False, f"object is not openable: {target['objectId']}"
        target["isOpen"] = action_dict["action"] == "OpenObject"
        return True, ""

    def _dirty_clean_object(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        target, error = self._target(action_dict)
        if target is None:
            return False, error
        if not target["dirtyable"]:
            return False, f"object is not dirtyable: {target['objectId']}"
        target["isDirty"] = action_dict["action"] == "DirtyObject"
        return True, ""

    def _move_ahead(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        magnitude = float(action_dict.get("moveMagnitude", 0.25))
        yaw = math.radians(float(self._agent["rotation"]["y"]))
        self._agent["position"]["x"] += magnitude * math.sin(yaw)
        self._agent["position"]["z"] += magnitude * math.cos(yaw)
        return True, ""

    def _rotate(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        degrees = float(action_dict.get("degrees", 90.0))
        direction = -1.0 if action_dict["action"] == "RotateLeft" else 1.0
        self._agent["rotation"]["y"] = (self._agent["rotation"]["y"] + direction * degrees) % 360
        return True, ""

    def _look(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        degrees = float(action_dict.get("degrees", 30.0))
        direction = -1.0 if action_dict["action"] == "LookUp" else 1.0
        new_horizon = self._agent["cameraHorizon"] + direction * degrees
        self._agent["cameraHorizon"] = max(-90.0, min(90.0, new_horizon))
        return True, ""

    def _refresh_receptacle_contents(self) -> None:
        for obj in self._objects.values():
            obj["receptacleObjectIds"] = []
        for obj in self._objects.values():
            if obj["isPickedUp"]:
                continue
            for parent_id in obj["parentReceptacles"]:
                parent = self._objects.get(parent_id)
                if parent is not None and parent["receptacle"]:
                    parent["receptacleObjectIds"].append(obj["objectId"])

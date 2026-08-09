"""Deterministic full- or partially-observable AI2-THOR-like mock kitchen."""

from __future__ import annotations

import math
import random
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
    region: str,
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
        "region": region,
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
    """Deterministic state mock with an optional partial-observability mode.

    Fully observable mode preserves the Phase 0–2 regression harness. Partial
    mode assigns Apple, Knife, and Plate to distinct seeded regions, filters the
    agent event to the current view, and enforces visibility/reachability before
    interaction. Full state remains accessible only through the explicitly
    privileged evaluator interface.
    """

    DEFAULT_SCENE = "MockKitchen"
    REGIONS = ("Kitchen", "DiningArea", "SinkArea")
    REGION_ANCHORS = {
        "Kitchen": (0.0, 0.0),
        "DiningArea": (10.0, 0.0),
        "SinkArea": (-10.0, 0.0),
    }
    VIEW_HALF_ANGLE_DEGREES = 50.0
    INTERACTION_DISTANCE = 2.25

    def __init__(self, *, partial_observability: bool = False, layout_seed: int = 0) -> None:
        self.partial_observability = partial_observability
        self.layout_seed = layout_seed
        self._scene_name = self.DEFAULT_SCENE
        self._objects: dict[str, dict[str, Any]] = {}
        self._agent: dict[str, Any] = {}
        self._held_object_id: str | None = None
        self._last_event: MockEvent | None = None
        self._last_action = "Reset"
        self._last_success = True
        self._last_error = ""
        self.reset(self.DEFAULT_SCENE)

    @property
    def last_event(self) -> MockEvent:
        """Return the most recent agent-facing mock event."""

        if self._last_event is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("Mock environment has not been reset")
        return self._last_event

    def reset(self, scene: str = DEFAULT_SCENE) -> MockEvent:
        """Restore the deterministic scene and seeded partial layout."""

        self._scene_name = scene or self.DEFAULT_SCENE
        if self.partial_observability:
            self._build_partial_layout()
        else:
            self._build_fully_observable_layout()
        self._held_object_id = None
        self._last_action = "Reset"
        self._last_success = True
        self._last_error = ""
        self._refresh_receptacle_contents()
        self._refresh_visibility()
        self._last_event = self._make_event()
        return self._last_event

    def step(self, action_dict: Mapping[str, Any]) -> MockEvent:
        """Execute a supported action and return the agent-facing event."""

        if not isinstance(action_dict, Mapping):
            return self._finish("Unknown", False, "action_schema_error: action must be a mapping")

        action = str(action_dict.get("action", "")).strip()
        if not action:
            return self._finish("Unknown", False, "action_schema_error: missing action name")

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
            "MoveToRegion": self._move_to_region,
            "RotateLeft": self._rotate,
            "RotateRight": self._rotate,
            "LookUp": self._look,
            "LookDown": self._look,
        }
        handler = handlers.get(action)
        if handler is None:
            return self._finish(action, False, f"unsupported_action: {action}")

        success, error = handler(action_dict)
        return self._finish(action, success, error)

    def get_observation(self) -> dict[str, Any]:
        """Return exactly the metadata available to the agent/planner."""

        return deepcopy(self.last_event.metadata)

    def get_evaluator_state(self) -> dict[str, Any]:
        """Return privileged full state for success checking and offline QA."""

        return self._make_metadata(include_hidden=True)

    def get_visible_objects(self) -> list[dict[str, Any]]:
        """Return defensive copies of currently visible objects."""

        return [deepcopy(obj) for obj in self._objects.values() if obj["visible"]]

    def get_all_objects(self) -> list[dict[str, Any]]:
        """Return privileged defensive copies of every scene object."""

        return [deepcopy(obj) for obj in self._objects.values()]

    def get_agent_state(self) -> dict[str, Any]:
        """Return a defensive copy of the current agent pose and region."""

        return deepcopy(self._agent)

    def save_frame(self, path: str | Path) -> Path:
        """Explain that this controlled state mock does not render RGB frames."""

        raise RuntimeError(f"MockEnv does not render frames; cannot save {Path(path)}")

    def _build_fully_observable_layout(self) -> None:
        countertop = "CounterTop|1"
        self._objects = {
            countertop: _object(
                "CounterTop", countertop, _position(0.0, 0.9, 1.5), region="Kitchen", receptacle=True
            ),
            "Plate|1": _object(
                "Plate",
                "Plate|1",
                _position(0.25, 0.95, 1.5),
                region="Kitchen",
                pickupable=True,
                receptacle=True,
                parent_receptacles=[countertop],
            ),
            "Apple|1": _object(
                "Apple",
                "Apple|1",
                _position(-0.2, 0.95, 1.5),
                region="Kitchen",
                pickupable=True,
                sliceable=True,
                dirtyable=True,
            ),
            "Knife|1": _object(
                "Knife",
                "Knife|1",
                _position(0.55, 0.95, 1.5),
                region="Kitchen",
                pickupable=True,
                parent_receptacles=[countertop],
            ),
            "SinkBasin|1": _object(
                "SinkBasin", "SinkBasin|1", _position(-1.0, 0.85, 1.2), region="Kitchen", receptacle=True
            ),
            "Faucet|1": _object(
                "Faucet", "Faucet|1", _position(-1.0, 1.1, 1.1), region="Kitchen", toggleable=True
            ),
            "Cabinet|1": _object(
                "Cabinet",
                "Cabinet|1",
                _position(1.2, 1.1, 1.3),
                region="Kitchen",
                receptacle=True,
                openable=True,
            ),
        }
        self._agent = {
            "position": _position(0.0, 0.9, 0.0),
            "rotation": _position(0.0, 0.0, 0.0),
            "cameraHorizon": 0.0,
            "isStanding": True,
            "region": "Kitchen",
        }

    def _build_partial_layout(self) -> None:
        shuffled_regions = list(self.REGIONS)
        random.Random(self.layout_seed).shuffle(shuffled_regions)
        assignments = dict(zip(("Apple", "Knife", "Plate"), shuffled_regions, strict=True))

        def located(region: str, x_offset: float = 0.0, z_offset: float = 1.4) -> dict[str, float]:
            anchor_x, anchor_z = self.REGION_ANCHORS[region]
            return _position(anchor_x + x_offset, 0.95, anchor_z + z_offset)

        self._objects = {
            "CounterTop|1": _object(
                "CounterTop",
                "CounterTop|1",
                located("Kitchen"),
                region="Kitchen",
                receptacle=True,
            ),
            "Plate|1": _object(
                "Plate",
                "Plate|1",
                located(assignments["Plate"], 0.25),
                region=assignments["Plate"],
                pickupable=True,
                receptacle=True,
            ),
            "Apple|1": _object(
                "Apple",
                "Apple|1",
                located(assignments["Apple"], -0.2),
                region=assignments["Apple"],
                pickupable=True,
                sliceable=True,
                dirtyable=True,
            ),
            "Knife|1": _object(
                "Knife",
                "Knife|1",
                located(assignments["Knife"], 0.5),
                region=assignments["Knife"],
                pickupable=True,
            ),
            "SinkBasin|1": _object(
                "SinkBasin",
                "SinkBasin|1",
                located("SinkArea", -0.25),
                region="SinkArea",
                receptacle=True,
            ),
            "Faucet|1": _object(
                "Faucet",
                "Faucet|1",
                located("SinkArea", 0.25),
                region="SinkArea",
                toggleable=True,
            ),
            "Cabinet|1": _object(
                "Cabinet",
                "Cabinet|1",
                located("Kitchen", 0.7),
                region="Kitchen",
                receptacle=True,
                openable=True,
            ),
        }
        start_region = assignments["Apple"]
        start_x, start_z = self.REGION_ANCHORS[start_region]
        self._agent = {
            "position": _position(start_x, 0.9, start_z),
            "rotation": _position(0.0, 0.0, 0.0),
            "cameraHorizon": 0.0,
            "isStanding": True,
            "region": start_region,
        }

    def _make_event(self) -> MockEvent:
        return MockEvent(metadata=self._make_metadata(include_hidden=not self.partial_observability))

    def _make_metadata(self, *, include_hidden: bool) -> dict[str, Any]:
        objects = self.get_all_objects() if include_hidden else self.get_visible_objects()
        inventory = []
        if self._held_object_id:
            inventory.append(deepcopy(self._objects[self._held_object_id]))
        return {
            "sceneName": self._scene_name,
            "objects": objects,
            "agent": self.get_agent_state(),
            "inventoryObjects": inventory,
            "lastAction": self._last_action,
            "lastActionSuccess": self._last_success,
            "errorMessage": self._last_error,
            "actionReturn": None,
            "partialObservability": self.partial_observability,
            "layoutSeed": self.layout_seed,
            "availableRegions": list(self.REGIONS),
        }

    def _finish(self, action: str, success: bool, error: str) -> MockEvent:
        self._last_action = action
        self._last_success = success
        self._last_error = error
        self._refresh_receptacle_contents()
        self._refresh_visibility()
        self._last_event = self._make_event()
        return self._last_event

    def _target(self, action_dict: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
        object_id = str(action_dict.get("objectId", "")).strip()
        if not object_id:
            return None, "action_schema_error: missing objectId"
        target = self._objects.get(object_id)
        if target is None:
            return None, f"unknown_object: {object_id}"
        if not target["visible"]:
            return None, f"object_not_visible: {object_id}"
        if self._distance_to(target) > self.INTERACTION_DISTANCE:
            return None, f"not_in_interaction_range: {object_id}"
        return target, ""

    def _pass(self, _: Mapping[str, Any]) -> tuple[bool, str]:
        return True, ""

    def _pickup_object(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        target, error = self._target(action_dict)
        if target is None:
            return False, error
        if self._held_object_id:
            return False, f"inventory_not_empty: {self._held_object_id}"
        if not target["pickupable"]:
            return False, f"object_not_pickupable: object is not pickupable: {target['objectId']}"

        target["isPickedUp"] = True
        target["parentReceptacles"] = []
        target["region"] = self._agent["region"]
        target["position"] = deepcopy(self._agent["position"])
        self._held_object_id = target["objectId"]
        return True, ""

    def _put_object(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        receptacle, error = self._target(action_dict)
        if receptacle is None:
            return False, error
        if not self._held_object_id:
            return False, "inventory_empty: PutObject requires a held object"
        if not receptacle["receptacle"]:
            return False, f"target_not_receptacle: {receptacle['objectId']}"
        if receptacle["openable"] and not receptacle["isOpen"]:
            return False, f"receptacle_closed: {receptacle['objectId']}"

        held = self._objects[self._held_object_id]
        held["isPickedUp"] = False
        held["parentReceptacles"] = [receptacle["objectId"]]
        held["position"] = deepcopy(receptacle["position"])
        held["region"] = receptacle["region"]
        self._held_object_id = None
        return True, ""

    def _drop_hand_object(self, _: Mapping[str, Any]) -> tuple[bool, str]:
        if not self._held_object_id:
            return False, "inventory_empty: DropHandObject requires a held object"
        held = self._objects[self._held_object_id]
        held["isPickedUp"] = False
        held["parentReceptacles"] = []
        held["position"] = deepcopy(self._agent["position"])
        held["region"] = self._agent["region"]
        self._held_object_id = None
        return True, ""

    def _slice_object(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        target, error = self._target(action_dict)
        if target is None:
            return False, error
        if not target["sliceable"]:
            return False, f"object_not_sliceable: {target['objectId']}"
        if not self._held_object_id or self._objects[self._held_object_id]["objectType"] != "Knife":
            return False, "knife_required: a Knife must be held"
        target["isSliced"] = True
        return True, ""

    def _toggle_object(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        target, error = self._target(action_dict)
        if target is None:
            return False, error
        if not target["toggleable"]:
            return False, f"object_not_toggleable: {target['objectId']}"
        target["isToggled"] = action_dict["action"] == "ToggleObjectOn"
        if target["objectType"] == "Faucet" and target["isToggled"]:
            for obj in self._objects.values():
                if obj["dirtyable"] and any(
                    self._objects.get(parent_id, {}).get("objectType") == "SinkBasin"
                    for parent_id in obj["parentReceptacles"]
                ):
                    obj["isDirty"] = False
        return True, ""

    def _open_close_object(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        target, error = self._target(action_dict)
        if target is None:
            return False, error
        if not target["openable"]:
            return False, f"object_not_openable: {target['objectId']}"
        target["isOpen"] = action_dict["action"] == "OpenObject"
        return True, ""

    def _dirty_clean_object(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        target, error = self._target(action_dict)
        if target is None:
            return False, error
        if not target["dirtyable"]:
            return False, f"object_not_dirtyable: {target['objectId']}"
        target["isDirty"] = action_dict["action"] == "DirtyObject"
        return True, ""

    def _move_ahead(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        magnitude = float(action_dict.get("moveMagnitude", 0.25))
        yaw = math.radians(float(self._agent["rotation"]["y"]))
        self._agent["position"]["x"] += magnitude * math.sin(yaw)
        self._agent["position"]["z"] += magnitude * math.cos(yaw)
        self._sync_held_object_pose()
        return True, ""

    def _move_to_region(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        region = str(action_dict.get("region", "")).strip()
        if not region:
            return False, "action_schema_error: MoveToRegion requires region"
        if region not in self.REGIONS:
            return False, f"unknown_region: {region}"
        anchor_x, anchor_z = self.REGION_ANCHORS[region]
        self._agent["region"] = region
        self._agent["position"] = _position(anchor_x, 0.9, anchor_z)
        self._agent["rotation"]["y"] = 0.0
        self._sync_held_object_pose()
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

    def _sync_held_object_pose(self) -> None:
        if self._held_object_id:
            held = self._objects[self._held_object_id]
            held["region"] = self._agent["region"]
            held["position"] = deepcopy(self._agent["position"])

    def _distance_to(self, obj: Mapping[str, Any]) -> float:
        position = obj["position"]
        agent_position = self._agent["position"]
        return math.sqrt(
            (float(position["x"]) - float(agent_position["x"])) ** 2
            + (float(position["z"]) - float(agent_position["z"])) ** 2
        )

    def _refresh_visibility(self) -> None:
        if not self.partial_observability:
            for obj in self._objects.values():
                obj["visible"] = True
            return

        agent_region = self._agent["region"]
        yaw = float(self._agent["rotation"]["y"])
        for obj in self._objects.values():
            if obj["isPickedUp"]:
                obj["visible"] = True
                continue
            if obj["region"] != agent_region:
                obj["visible"] = False
                continue
            dx = float(obj["position"]["x"]) - float(self._agent["position"]["x"])
            dz = float(obj["position"]["z"]) - float(self._agent["position"]["z"])
            bearing = math.degrees(math.atan2(dx, dz)) % 360
            angular_difference = ((bearing - yaw + 180) % 360) - 180
            obj["visible"] = abs(angular_difference) <= self.VIEW_HALF_ANGLE_DEGREES

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

"""Behavior tests for the deterministic mock kitchen."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env.mock_env import MockEnv  # noqa: E402


def by_id(env: MockEnv, object_id: str) -> dict:
    return next(obj for obj in env.get_all_objects() if obj["objectId"] == object_id)


class MockEnvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = MockEnv()

    def test_reset_exposes_expected_kitchen_objects(self) -> None:
        object_types = {obj["objectType"] for obj in self.env.get_all_objects()}

        self.assertTrue({"Apple", "CounterTop", "Plate", "SinkBasin", "Knife"} <= object_types)
        self.assertEqual(len(self.env.get_all_objects()), len(self.env.get_visible_objects()))

    def test_pickup_and_put_updates_object_and_receptacle_state(self) -> None:
        pickup = self.env.step({"action": "PickupObject", "objectId": "Apple|1"})
        put = self.env.step({"action": "PutObject", "objectId": "Plate|1"})

        apple = by_id(self.env, "Apple|1")
        plate = by_id(self.env, "Plate|1")
        self.assertTrue(pickup.metadata["lastActionSuccess"])
        self.assertTrue(put.metadata["lastActionSuccess"])
        self.assertFalse(apple["isPickedUp"])
        self.assertEqual(["Plate|1"], apple["parentReceptacles"])
        self.assertIn("Apple|1", plate["receptacleObjectIds"])
        self.assertEqual([], put.metadata["inventoryObjects"])

    def test_invalid_interaction_returns_error_without_crashing(self) -> None:
        event = self.env.step({"action": "PickupObject", "objectId": "CounterTop|1"})

        self.assertFalse(event.metadata["lastActionSuccess"])
        self.assertIn("not pickupable", event.metadata["errorMessage"])

    def test_slice_requires_held_knife(self) -> None:
        failed = self.env.step({"action": "SliceObject", "objectId": "Apple|1"})
        self.env.step({"action": "PickupObject", "objectId": "Knife|1"})
        succeeded = self.env.step({"action": "SliceObject", "objectId": "Apple|1"})

        self.assertFalse(failed.metadata["lastActionSuccess"])
        self.assertTrue(succeeded.metadata["lastActionSuccess"])
        self.assertTrue(by_id(self.env, "Apple|1")["isSliced"])

    def test_navigation_updates_agent_state(self) -> None:
        self.env.step({"action": "RotateRight"})
        self.env.step({"action": "MoveAhead", "moveMagnitude": 0.5})

        state = self.env.get_agent_state()
        self.assertEqual(90.0, state["rotation"]["y"])
        self.assertAlmostEqual(0.5, state["position"]["x"])

    def test_returned_objects_are_defensive_copies(self) -> None:
        objects = self.env.get_all_objects()
        objects[0]["visible"] = False

        self.assertTrue(self.env.get_all_objects()[0]["visible"])


if __name__ == "__main__":
    unittest.main()

"""Adapter tests that do not require the optional AI2-THOR package."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env.thor_env import ThorEnv  # noqa: E402


class FakeEvent:
    def __init__(self, metadata: dict) -> None:
        self.metadata = metadata
        self.frame = None


class FakeController:
    def __init__(self) -> None:
        self.last_event = FakeEvent({"objects": [], "agent": {}})
        self.stopped = False

    def reset(self, *, scene: str) -> FakeEvent:
        self.last_event = FakeEvent(
            {
                "sceneName": scene,
                "objects": [
                    {"objectId": "Apple|1", "visible": True},
                    {"objectId": "Knife|1", "visible": False},
                ],
                "agent": {"cameraHorizon": 0},
            }
        )
        return self.last_event

    def step(self, **action: object) -> FakeEvent:
        self.last_event.metadata["lastAction"] = action["action"]
        return self.last_event

    def stop(self) -> None:
        self.stopped = True


class ThorEnvAdapterTests(unittest.TestCase):
    def test_injected_controller_supports_interface(self) -> None:
        controller = FakeController()
        env = ThorEnv(controller=controller)

        event = env.reset("FloorPlan1")
        stepped = env.step({"action": "Pass"})

        self.assertEqual("FloorPlan1", event.metadata["sceneName"])
        self.assertEqual(["Apple|1"], [obj["objectId"] for obj in env.get_visible_objects()])
        self.assertEqual("Pass", stepped.metadata["lastAction"])
        self.assertEqual({"cameraHorizon": 0}, env.get_agent_state())
        self.assertEqual(
            ["Apple|1"],
            [obj["objectId"] for obj in env.get_observation()["objects"]],
        )
        self.assertEqual(
            {"Apple|1", "Knife|1"},
            {obj["objectId"] for obj in env.get_evaluator_state()["objects"]},
        )

    def test_close_stops_injected_controller(self) -> None:
        controller = FakeController()
        env = ThorEnv(controller=controller)

        env.close()

        self.assertTrue(controller.stopped)

    def test_step_before_reset_has_actionable_error(self) -> None:
        env = ThorEnv()

        with self.assertRaisesRegex(RuntimeError, "call reset"):
            env.step({"action": "Pass"})


if __name__ == "__main__":
    unittest.main()

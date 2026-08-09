"""Tests for action schema validation and execution normalization."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.actions import ActionExecutor, ActionSpace  # noqa: E402
from embodied_memory_thor.env.mock_env import MockEnv  # noqa: E402


class ActionExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = MockEnv()
        self.executor = ActionExecutor(ActionSpace())

    def test_schema_rejects_missing_object_id(self) -> None:
        result = self.executor.execute(self.env, {"action": "PickupObject"})

        self.assertFalse(result.success)
        self.assertTrue(result.invalid_action)
        self.assertIn("requires objectId", result.error_message)

    def test_environment_failure_is_normalized(self) -> None:
        result = self.executor.execute(
            self.env,
            {"action": "PickupObject", "objectId": "CounterTop|1"},
        )

        self.assertFalse(result.success)
        self.assertTrue(result.invalid_action)
        self.assertIn("not pickupable", result.error_message)

    def test_valid_action_returns_event(self) -> None:
        result = self.executor.execute(
            self.env,
            {"action": "PickupObject", "objectId": "Apple|1"},
        )

        self.assertTrue(result.success)
        self.assertFalse(result.invalid_action)
        self.assertIsNotNone(result.event)


if __name__ == "__main__":
    unittest.main()

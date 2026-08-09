"""Tests for Phase 2 task loading, availability, and state goals."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env.mock_env import MockEnv  # noqa: E402
from embodied_memory_thor.evaluation import (  # noqa: E402
    TaskDefinition,
    check_object_availability,
    evaluate_task_success,
    load_task,
    load_tasks,
)


class TaskConfigurationTests(unittest.TestCase):
    def test_all_four_tasks_load_with_required_fields(self) -> None:
        tasks = load_tasks()

        self.assertEqual(
            {
                "put_apple_on_countertop",
                "put_apple_on_plate",
                "wash_apple_put_countertop",
                "slice_apple_put_plate",
            },
            set(tasks),
        )
        for task in tasks.values():
            self.assertTrue(task.natural_language_instruction)
            self.assertTrue(task.required_objects)
            self.assertTrue(task.goal_conditions)
            self.assertGreater(task.max_steps, 0)

    def test_unknown_task_has_available_choices(self) -> None:
        with self.assertRaisesRegex(KeyError, "available tasks"):
            load_task("does_not_exist")


class AvailabilityAndSuccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = MockEnv()

    def test_mock_scene_satisfies_configured_requirements(self) -> None:
        for task in load_tasks().values():
            result = check_object_availability(task, self.env.last_event)
            self.assertTrue(result.available, (task.task_name, result.missing_object_types))

    def test_missing_required_type_is_reported(self) -> None:
        task = TaskDefinition(
            task_name="impossible",
            natural_language_instruction="Find a microwave.",
            required_objects=("Microwave",),
            goal_conditions=(
                {
                    "type": "object_state",
                    "object_type": "Microwave",
                    "field": "isOpen",
                    "equals": True,
                },
            ),
            max_steps=1,
        )

        result = check_object_availability(task, self.env.last_event)

        self.assertFalse(result.available)
        self.assertEqual(("Microwave",), result.missing_object_types)

    def test_success_depends_on_environment_parent_state(self) -> None:
        task = load_task("put_apple_on_plate")

        before = evaluate_task_success(task, self.env.last_event)
        self.env.step({"action": "PickupObject", "objectId": "Apple|1"})
        event = self.env.step({"action": "PutObject", "objectId": "Plate|1"})
        after = evaluate_task_success(task, event)

        self.assertFalse(before.success)
        self.assertTrue(after.success)

    def test_wash_goal_requires_clean_and_placed_state(self) -> None:
        task = load_task("wash_apple_put_countertop")
        self.env.step({"action": "PickupObject", "objectId": "Apple|1"})
        self.env.step({"action": "PutObject", "objectId": "CounterTop|1"})

        result = evaluate_task_success(task, self.env.last_event)

        self.assertFalse(result.success)
        self.assertTrue(any("isDirty=False" in item for item in result.unmet_conditions))


if __name__ == "__main__":
    unittest.main()

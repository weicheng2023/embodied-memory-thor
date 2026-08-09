"""Research-boundary tests for the controlled partially observable mock."""

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
from embodied_memory_thor.env.object_parser import parse_objects  # noqa: E402
from embodied_memory_thor.evaluation import evaluate_task_success, load_task  # noqa: E402
from embodied_memory_thor.planners import ObservationOnlyPlanner, OracleDebugPlanner  # noqa: E402


class PartialObservationBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = MockEnv(partial_observability=True, layout_seed=0)

    def test_agent_observation_is_strict_subset_of_evaluator_state(self) -> None:
        observed_ids = {obj["objectId"] for obj in parse_objects(self.env.get_observation())}
        evaluator_ids = {obj["objectId"] for obj in parse_objects(self.env.get_evaluator_state())}

        self.assertIn("Apple|1", observed_ids)
        self.assertLess(len(observed_ids), len(evaluator_ids))
        self.assertTrue(observed_ids < evaluator_ids)

    def test_region_move_removes_previously_seen_apple_from_observation(self) -> None:
        start_region = self.env.get_agent_state()["region"]
        destination = next(region for region in self.env.REGIONS if region != start_region)

        event = self.env.step({"action": "MoveToRegion", "region": destination})
        observed_ids = {obj["objectId"] for obj in parse_objects(event)}

        self.assertNotIn("Apple|1", observed_ids)
        self.assertEqual(destination, event.metadata["agent"]["region"])

    def test_rotation_changes_current_view(self) -> None:
        before = {obj["objectId"] for obj in parse_objects(self.env.get_observation())}

        event = self.env.step({"action": "RotateRight", "degrees": 180})
        after = {obj["objectId"] for obj in parse_objects(event)}

        self.assertTrue(before)
        self.assertFalse(after)

    def test_hidden_object_cannot_be_targeted_by_id(self) -> None:
        hidden_id = next(
            obj["objectId"]
            for obj in self.env.get_all_objects()
            if not obj["visible"] and obj["pickupable"]
        )

        event = self.env.step({"action": "PickupObject", "objectId": hidden_id})

        self.assertFalse(event.metadata["lastActionSuccess"])
        self.assertEqual(f"object_not_visible: {hidden_id}", event.metadata["errorMessage"])

    def test_visible_but_distant_object_is_not_reachable(self) -> None:
        self.env.step({"action": "MoveAhead", "moveMagnitude": -3.0})

        event = self.env.step({"action": "PickupObject", "objectId": "Apple|1"})

        self.assertFalse(event.metadata["lastActionSuccess"])
        self.assertIn("not_in_interaction_range", event.metadata["errorMessage"])

    def test_seeded_layout_is_reproducible_and_key_objects_are_separated(self) -> None:
        first = MockEnv(partial_observability=True, layout_seed=7)
        second = MockEnv(partial_observability=True, layout_seed=7)

        first_regions = {
            obj["objectType"]: obj["region"]
            for obj in first.get_all_objects()
            if obj["objectType"] in {"Apple", "Knife", "Plate"}
        }
        second_regions = {
            obj["objectType"]: obj["region"]
            for obj in second.get_all_objects()
            if obj["objectType"] in {"Apple", "Knife", "Plate"}
        }

        self.assertEqual(first_regions, second_regions)
        self.assertEqual(3, len(set(first_regions.values())))


class PartialPlannerTests(unittest.TestCase):
    def _run(self, planner, *, seed: int, privileged: bool) -> tuple[int, int]:
        task = load_task("po_slice_apple_put_plate")
        env = MockEnv(partial_observability=True, layout_seed=seed)
        executor = ActionExecutor(ActionSpace())
        moves = 0

        for step in range(1, task.max_steps + 1):
            observation = env.get_observation()
            evaluator_state = env.get_evaluator_state()
            if evaluate_task_success(task, evaluator_state).success:
                return step - 1, moves

            action = planner.plan(
                task,
                observation,
                evaluator_state=evaluator_state if privileged else None,
            )
            self.assertIsNotNone(action)
            if not privileged and action and "objectId" in action:
                observed_ids = {obj["objectId"] for obj in parse_objects(observation)}
                self.assertIn(action["objectId"], observed_ids)
            if action and action.get("action") == "MoveToRegion":
                moves += 1
            result = executor.execute(env, action or {})
            self.assertTrue(result.success, result.error_message)

        self.assertTrue(evaluate_task_success(task, env.get_evaluator_state()).success)
        return task.max_steps, moves

    def test_no_memory_search_and_oracle_solve_seeded_tasks(self) -> None:
        for seed in (0, 1, 2):
            with self.subTest(seed=seed):
                no_memory_steps, no_memory_moves = self._run(
                    ObservationOnlyPlanner(), seed=seed, privileged=False
                )
                oracle_steps, oracle_moves = self._run(
                    OracleDebugPlanner(), seed=seed, privileged=True
                )

                self.assertLessEqual(oracle_steps, no_memory_steps)
                self.assertLessEqual(oracle_moves, no_memory_moves)


if __name__ == "__main__":
    unittest.main()

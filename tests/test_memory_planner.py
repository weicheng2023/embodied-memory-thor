"""Fairness and two-task tests for the shared memory-aware planner."""

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
from embodied_memory_thor.evaluation import (  # noqa: E402
    TaskProgressTracker,
    evaluate_task_success,
    load_task,
)
from embodied_memory_thor.memory import build_memory_provider  # noqa: E402
from embodied_memory_thor.planners import MemoryAwarePlanner  # noqa: E402


LAYOUT_SEEDS = (0, 1, 4, 5, 6, 7)
VARIANTS = ("no_memory", "short_memory", "object_memory")


class SharedPlannerParityTests(unittest.TestCase):
    def test_all_variants_have_identical_fallback_when_target_has_no_record(self) -> None:
        task = load_task("po_slice_apple_put_plate")
        env = MockEnv(partial_observability=True, layout_seed=0)
        observation = env.get_observation()
        actions = []
        traces = []

        for variant in VARIANTS:
            provider = build_memory_provider(variant)
            provider.observe(
                step=0,
                observation=observation,
                action={"action": "Reset"},
                success=True,
                error="",
                observation_id="reset:0",
            )
            planner = MemoryAwarePlanner()
            actions.append(planner.plan(task, observation, memory=provider))
            traces.append(planner.trace_snapshot())

        self.assertEqual(actions[0], actions[1])
        self.assertEqual(actions[0], actions[2])
        self.assertTrue(all(trace["decision_source"] == "systematic_fallback" for trace in traces))

    def test_action_space_is_shared_and_intervention_is_not_an_action(self) -> None:
        action_space = ActionSpace()
        self.assertNotIn("RelocateObject", action_space.allowed_actions)
        self.assertNotIn("relocate_object_for_experiment", action_space.allowed_actions)


class PartialTaskStructureTests(unittest.TestCase):
    def test_book_and_lamp_follow_distinct_seeded_roles(self) -> None:
        signatures = set()
        for seed in LAYOUT_SEEDS:
            env = MockEnv(partial_observability=True, layout_seed=seed)
            regions = {obj["objectType"]: obj["region"] for obj in env.get_all_objects()}
            self.assertEqual(regions["Apple"], regions["Book"])
            self.assertEqual(regions["Knife"], regions["DeskLamp"])
            self.assertNotEqual(regions["Book"], regions["DeskLamp"])
            signatures.add((regions["Apple"], regions["Knife"], regions["Plate"]))
        self.assertEqual(6, len(signatures))

    def _run(self, task_name: str, variant: str, seed: int) -> tuple[int, int, dict]:
        task = load_task(task_name)
        env = MockEnv(partial_observability=True, layout_seed=seed)
        provider = build_memory_provider(variant)
        planner = MemoryAwarePlanner()
        progress = TaskProgressTracker(task)
        executor = ActionExecutor(ActionSpace())
        observation = env.get_observation()
        provider.observe(
            step=0,
            observation=observation,
            action={"action": "Reset"},
            success=True,
            error="",
            observation_id="reset:0",
        )
        memory_guided = 0

        for step in range(1, task.max_steps + 1):
            if evaluate_task_success(task, env.get_evaluator_state()).success:
                return step - 1, memory_guided, progress.snapshot()
            action = planner.plan(task, observation, memory=provider, task_progress=progress)
            self.assertIsNotNone(action)
            trace = planner.trace_snapshot()
            memory_guided += trace["decision_source"] == "memory_hint"
            if action and "objectId" in action:
                visible_ids = {obj["objectId"] for obj in parse_objects(observation)}
                self.assertIn(action["objectId"], visible_ids)
            result = executor.execute(env, action or {})
            self.assertTrue(result.success, result.error_message)
            observation = env.get_observation()
            progress.observe_action(
                step=step,
                action=action or {},
                success=result.success,
                observation_after=observation,
            )
            provider.observe(
                step=step,
                observation=observation,
                action=action or {},
                success=result.success,
                error=result.error_message,
                observation_id=f"step:{step}",
            )

        self.assertTrue(evaluate_task_success(task, env.get_evaluator_state()).success)
        return task.max_steps, memory_guided, progress.snapshot()

    def test_all_variants_solve_both_tasks_on_full_layout_panel(self) -> None:
        guided_by_task = {
            "po_slice_apple_put_plate": 0,
            "po_find_book_after_distraction": 0,
        }
        for task_name in guided_by_task:
            for variant in VARIANTS:
                for seed in LAYOUT_SEEDS:
                    with self.subTest(task=task_name, variant=variant, seed=seed):
                        _, guided, progress = self._run(task_name, variant, seed)
                        if variant == "object_memory":
                            guided_by_task[task_name] += guided
                        if task_name == "po_find_book_after_distraction":
                            self.assertTrue(progress["ordered_subgoal_passed"])
                            self.assertFalse(progress["protocol_violations"])
        self.assertGreater(guided_by_task["po_slice_apple_put_plate"], 0)
        self.assertGreater(guided_by_task["po_find_book_after_distraction"], 0)


if __name__ == "__main__":
    unittest.main()

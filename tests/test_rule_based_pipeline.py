"""End-to-end in-memory checks for the transparent rule baseline."""

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
from embodied_memory_thor.evaluation import evaluate_task_success, load_tasks  # noqa: E402
from embodied_memory_thor.planners import RuleBasedPlanner  # noqa: E402


class RuleBasedPipelineTests(unittest.TestCase):
    def test_all_configured_mock_tasks_reach_state_goals(self) -> None:
        planner = RuleBasedPlanner()
        executor = ActionExecutor(ActionSpace())

        for task in load_tasks().values():
            with self.subTest(task=task.task_name):
                env = MockEnv()
                event = env.last_event
                actions: list[dict] = []
                for _ in range(task.max_steps):
                    if evaluate_task_success(task, event).success:
                        break
                    action = planner.plan(task, event)
                    self.assertIsNotNone(action)
                    actions.append(action or {})
                    result = executor.execute(env, action or {})
                    self.assertTrue(result.success, result.error_message)
                    event = result.event

                self.assertTrue(evaluate_task_success(task, event).success, actions)
                self.assertGreater(len(actions), 0)


if __name__ == "__main__":
    unittest.main()

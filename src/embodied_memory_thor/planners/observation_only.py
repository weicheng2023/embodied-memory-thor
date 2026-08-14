"""Compatibility wrapper for the shared planner with no historical memory."""

from __future__ import annotations

from embodied_memory_thor.memory.providers import NoMemoryProvider
from embodied_memory_thor.planners.memory_aware import MemoryAwarePlanner


class ObservationOnlyPlanner(MemoryAwarePlanner):
    """Use the shared task/search policy with an always-empty provider."""

    name = "rule_based_no_memory"

    def plan(self, task, observation, memory=None, action_space=None, evaluator_state=None, task_progress=None):
        del memory
        return super().plan(
            task,
            observation,
            memory=NoMemoryProvider(),
            action_space=action_space,
            evaluator_state=evaluator_state,
            task_progress=task_progress,
        )

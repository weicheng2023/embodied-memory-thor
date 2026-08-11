"""Evaluator-only intervention contract for real-THOR comparison conditions."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from embodied_memory_thor.env.base import EmbodiedEnv


class EvaluatorIntervention(Protocol):
    """Apply a matched hidden-state change outside the planner action space."""

    intervention_id: str

    def maybe_apply(
        self,
        *,
        env: EmbodiedEnv,
        task_name: str,
        step: int,
        task_stage: str,
        agent_action: Mapping[str, Any],
        agent_action_success: bool,
        pre_intervention_observation: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        """Return a private audit record when the frozen intervention fires."""

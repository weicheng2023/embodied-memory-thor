"""Action validation and exception-safe environment execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from embodied_memory_thor.actions.action_space import ActionSpace
from embodied_memory_thor.env.base import EmbodiedEnv
from embodied_memory_thor.env.object_parser import metadata_from_event


@dataclass(frozen=True)
class ExecutionResult:
    """Normalized outcome of one attempted environment action."""

    action: dict[str, Any]
    event: Any | None
    success: bool
    error_message: str
    invalid_action: bool


class ActionExecutor:
    """Prevent malformed actions and normalize environment failures."""

    def __init__(self, action_space: ActionSpace | None = None) -> None:
        self.action_space = action_space or ActionSpace()

    def execute(
        self,
        env: EmbodiedEnv,
        action_dict: Mapping[str, Any],
    ) -> ExecutionResult:
        """Validate and execute an action without leaking environment exceptions."""

        valid, validation_error = self.action_space.validate(action_dict)
        normalized_action = dict(action_dict) if isinstance(action_dict, Mapping) else {}
        if not valid:
            return ExecutionResult(
                action=normalized_action,
                event=None,
                success=False,
                error_message=validation_error,
                invalid_action=True,
            )

        try:
            event = env.step(normalized_action)
        except Exception as exc:
            return ExecutionResult(
                action=normalized_action,
                event=None,
                success=False,
                error_message=f"{type(exc).__name__}: {exc}",
                invalid_action=True,
            )

        metadata = metadata_from_event(event)
        success = bool(metadata.get("lastActionSuccess", True))
        error_message = str(metadata.get("errorMessage", "") or "")
        return ExecutionResult(
            action=normalized_action,
            event=event,
            success=success,
            error_message=error_message,
            invalid_action=not success,
        )

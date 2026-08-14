"""Supported Phase 2 action names and lightweight schema validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ActionSpace:
    """Validate structured actions before they reach an environment."""

    allowed_actions: frozenset[str] = frozenset(
        {
            "Pass",
            "MoveAhead",
            "MoveBack",
            "MoveToRegion",
            "RotateLeft",
            "RotateRight",
            "LookUp",
            "LookDown",
            "PickupObject",
            "PutObject",
            "DropHandObject",
            "SliceObject",
            "OpenObject",
            "CloseObject",
            "ToggleObjectOn",
            "ToggleObjectOff",
            "DirtyObject",
            "CleanObject",
        }
    )
    object_actions: frozenset[str] = frozenset(
        {
            "PickupObject",
            "PutObject",
            "SliceObject",
            "OpenObject",
            "CloseObject",
            "ToggleObjectOn",
            "ToggleObjectOff",
            "DirtyObject",
            "CleanObject",
        }
    )

    def validate(self, action_dict: Mapping[str, Any]) -> tuple[bool, str]:
        """Return whether an action has the minimum safe schema."""

        if not isinstance(action_dict, Mapping):
            return False, "action must be a mapping"
        action_name = str(action_dict.get("action", "")).strip()
        if not action_name:
            return False, "action is missing a non-empty 'action' name"
        if action_name not in self.allowed_actions:
            return False, f"unsupported action: {action_name}"
        if action_name in self.object_actions and not str(action_dict.get("objectId", "")).strip():
            return False, f"{action_name} requires objectId"
        if action_name == "MoveToRegion" and not str(action_dict.get("region", "")).strip():
            return False, "MoveToRegion requires region"
        return True, ""

    def as_sorted_list(self) -> list[str]:
        """Return stable action names for logs and future prompts."""

        return sorted(self.allowed_actions)

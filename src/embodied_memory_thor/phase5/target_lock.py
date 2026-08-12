"""Shared planner-safe target lock and bounded transient-loss recovery."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


TARGET_LOCK_POLICY_VERSION = "phase5-shared-target-lock-v1"
TARGET_LOCK_RECOVERY_ACTION_BUDGET = 12
TARGET_LOCK_APPROACH_ACTION_BUDGET = 6


@dataclass
class TargetLockMetrics:
    target_visible_event_count: int = 0
    target_lock_entered_count: int = 0
    target_lock_pickup_attempt_count: int = 0
    transient_visibility_loss_count: int = 0
    local_recovery_action_count: int = 0
    target_reacquired_after_loss_count: int = 0
    picked_after_target_lock: bool = False
    target_lock_failed_reason: str = ""

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)


class SharedTargetLockPolicy:
    """Pause fallback after visible target evidence and recover locally if lost.

    State is derived only from planner-safe observations and this policy's own
    ordinary action results. It never consumes evaluator metadata, relocation
    destinations, anchor registries, or hidden object positions.
    """

    def __init__(
        self,
        *,
        target_type: str,
        recovery_action_budget: int = TARGET_LOCK_RECOVERY_ACTION_BUDGET,
        approach_action_budget: int = TARGET_LOCK_APPROACH_ACTION_BUDGET,
        visible_target_rotation_tolerance_degrees: float = 45.0,
    ) -> None:
        if not target_type.strip():
            raise ValueError("target_type must be non-empty")
        if recovery_action_budget < 1 or approach_action_budget < 1:
            raise ValueError("target-lock budgets must be positive")
        self.target_type = target_type
        self.recovery_action_budget = recovery_action_budget
        self.approach_action_budget = approach_action_budget
        self.visible_target_rotation_tolerance_degrees = (
            visible_target_rotation_tolerance_degrees
        )
        self.metrics = TargetLockMetrics()
        self.active = False
        self.recovering = False
        self._pickup_failed_while_visible = False
        self._approach_action_count = 0
        self._recovery_actions: list[str] = []
        self._recovery_cursor = 0
        self._last_directive: dict[str, Any] | None = None
        self._last_pre_action_visible = False
        self._suppress_until_target_hidden = False

    def next_directive(
        self,
        observation: Mapping[str, Any],
        *,
        allowed_actions: Sequence[str],
    ) -> dict[str, Any] | None:
        """Return one shared target-lock action, or ``None`` for normal fallback."""

        target = self._visible_target(observation)
        if self._suppress_until_target_hidden:
            if target is not None:
                return None
            self._suppress_until_target_hidden = False
        if target is not None:
            self.metrics.target_visible_event_count += 1
            if not self.active:
                self.active = True
                self.metrics.target_lock_entered_count += 1
                self._approach_action_count = 0
            if self.recovering:
                self.metrics.target_reacquired_after_loss_count += 1
                self.recovering = False
                self._recovery_actions = []
                self._recovery_cursor = 0
            if self._pickup_failed_while_visible:
                if self._approach_action_count >= self.approach_action_budget:
                    self._fail("bounded_approach_budget_exhausted")
                    return None
                action = self._approach_action(
                    observation, target, allowed_actions=allowed_actions
                )
                if action is None:
                    self._fail("no_bounded_approach_action_available")
                    return None
                self._approach_action_count += 1
                return self._directive(
                    action,
                    phase="bounded_approach",
                )
            object_id = str(target.get("objectId", ""))
            if not object_id or "PickupObject" not in allowed_actions:
                self._fail("visible_target_not_pickup_actionable")
                return None
            self.metrics.target_lock_pickup_attempt_count += 1
            return self._directive(
                {"action": "PickupObject", "objectId": object_id},
                phase="pickup_attempt",
            )

        if not self.active or not self.recovering:
            return None
        if self._recovery_cursor >= len(self._recovery_actions):
            self._fail("local_recovery_budget_exhausted")
            return None
        action_name = self._recovery_actions[self._recovery_cursor]
        recovery_index = self._recovery_cursor
        self._recovery_cursor += 1
        self.metrics.local_recovery_action_count += 1
        return self._directive(
            {"action": action_name},
            phase="local_recovery",
            recovery_action_index=recovery_index,
        )

    def record_result(
        self,
        directive: Mapping[str, Any],
        *,
        success: bool,
        error_message: str,
        observation_after: Mapping[str, Any],
        allowed_actions: Sequence[str],
    ) -> None:
        """Update lock state from an ordinary action result and safe observation."""

        action = directive.get("action", {})
        action_name = str(action.get("action", "")) if isinstance(action, Mapping) else ""
        visible_after = self._visible_target(observation_after) is not None
        inventory_after = observation_after.get("inventory", [])
        picked = action_name == "PickupObject" and success and any(
            isinstance(item, Mapping) and item.get("objectType") == self.target_type
            for item in inventory_after
        )
        if picked:
            self.metrics.picked_after_target_lock = True
            self.active = False
            self.recovering = False
            self._pickup_failed_while_visible = False
            self._suppress_until_target_hidden = False
            self._last_directive = deepcopy(dict(directive))
            self._last_pre_action_visible = True
            return

        if action_name == "PickupObject":
            if not success and visible_after:
                if self._recoverable_pickup_failure(error_message):
                    self._pickup_failed_while_visible = True
                else:
                    self._fail("pickup_failure_not_distance_or_angle_related")
                    return
            else:
                self._pickup_failed_while_visible = False
        elif directive.get("phase") == "bounded_approach" and visible_after:
            self._pickup_failed_while_visible = False

        if self._last_pre_action_visible and not visible_after:
            self.metrics.transient_visibility_loss_count += 1
            self.recovering = True
            self._pickup_failed_while_visible = False
            self._recovery_actions = self._build_recovery_actions(
                last_action=action_name,
                action_success=success,
                allowed_actions=allowed_actions,
            )
            self._recovery_cursor = 0
            if not self._recovery_actions:
                self._fail("no_local_recovery_action_available")
        elif directive.get("phase") == "local_recovery" and visible_after:
            self.metrics.target_reacquired_after_loss_count += 1
            self.recovering = False
            self._pickup_failed_while_visible = False
            self._recovery_actions = []
            self._recovery_cursor = 0
        elif (
            directive.get("phase") == "local_recovery"
            and not visible_after
            and self._recovery_cursor >= len(self._recovery_actions)
        ):
            self._fail("local_recovery_budget_exhausted")

        self._last_directive = deepcopy(dict(directive))
        self._last_pre_action_visible = visible_after

    def snapshot(self) -> dict[str, Any]:
        """Return coordinate-free metrics and bounded policy state."""

        return {
            "policy": TARGET_LOCK_POLICY_VERSION,
            "target_type": self.target_type,
            "recovery_action_budget": self.recovery_action_budget,
            "approach_action_budget": self.approach_action_budget,
            **self.metrics.snapshot(),
        }

    def _directive(
        self,
        action: Mapping[str, Any],
        *,
        phase: str,
        recovery_action_index: int | None = None,
    ) -> dict[str, Any]:
        directive = {
            "policy": TARGET_LOCK_POLICY_VERSION,
            "phase": phase,
            "target_object_type": self.target_type,
            "action": dict(action),
            "recovery_budget": self.recovery_action_budget,
            "recovery_action_index": recovery_action_index,
        }
        self._last_directive = deepcopy(directive)
        self._last_pre_action_visible = phase != "local_recovery"
        return directive

    def _visible_target(
        self, observation: Mapping[str, Any]
    ) -> Mapping[str, Any] | None:
        objects = observation.get("objects", [])
        if not isinstance(objects, list):
            return None
        return next(
            (
                item
                for item in objects
                if isinstance(item, Mapping)
                and item.get("visible") is True
                and item.get("pickupable") is True
                and item.get("objectType") == self.target_type
                and item.get("objectId")
            ),
            None,
        )

    def _approach_action(
        self,
        observation: Mapping[str, Any],
        target: Mapping[str, Any],
        *,
        allowed_actions: Sequence[str],
    ) -> dict[str, Any] | None:
        agent = observation.get("agent", {})
        current = agent.get("position", {}) if isinstance(agent, Mapping) else {}
        rotation = agent.get("rotation", {}) if isinstance(agent, Mapping) else {}
        target_position = target.get("position", {})
        if isinstance(current, Mapping) and isinstance(target_position, Mapping):
            try:
                dx = float(target_position["x"]) - float(current["x"])
                dz = float(target_position["z"]) - float(current["z"])
                yaw = float(rotation.get("y", 0.0)) if isinstance(rotation, Mapping) else 0.0
                target_yaw = math.degrees(math.atan2(dx, dz)) % 360.0
                delta = (target_yaw - yaw + 180.0) % 360.0 - 180.0
                if abs(delta) > self.visible_target_rotation_tolerance_degrees:
                    turn = "RotateRight" if delta > 0 else "RotateLeft"
                    if turn in allowed_actions:
                        return {"action": turn}
            except (KeyError, TypeError, ValueError):
                pass
        if "MoveAhead" in allowed_actions:
            return {"action": "MoveAhead"}
        return None

    def _build_recovery_actions(
        self,
        *,
        last_action: str,
        action_success: bool,
        allowed_actions: Sequence[str],
    ) -> list[str]:
        proposed: list[str] = []
        if last_action == "MoveAhead" and action_success and "MoveBack" in allowed_actions:
            proposed.append("MoveBack")
        proposed.extend(
            [
                "LookDown",
                "LookUp",
                "RotateLeft",
                "RotateRight",
                "RotateRight",
                "RotateLeft",
                "LookUp",
                "LookDown",
                "RotateRight",
                "RotateLeft",
                "RotateLeft",
                "RotateRight",
            ]
        )
        return [
            action
            for action in proposed
            if action in allowed_actions
        ][: self.recovery_action_budget]

    @staticmethod
    def _recoverable_pickup_failure(error_message: str) -> bool:
        normalized = error_message.casefold()
        return any(
            marker in normalized
            for marker in (
                "angle",
                "close enough",
                "distance",
                "far",
                "interact",
                "reach",
            )
        )

    def _fail(self, reason: str) -> None:
        self.metrics.target_lock_failed_reason = reason
        self.active = False
        self.recovering = False
        self._pickup_failed_while_visible = False
        self._suppress_until_target_hidden = True
        self._recovery_actions = []
        self._recovery_cursor = 0

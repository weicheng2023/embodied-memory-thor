"""Planner-safe progress state for the controlled real Book task."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


PHASE5_BOOK_DISTRACTION_POLICY_V1 = "phase5-book-distraction-v1"
PHASE5_BOOK_DISTRACTION_POLICY_V2 = "phase5-book-distraction-v2"
PHASE5_BOOK_DISTRACTION_POLICY_V3 = "phase5-book-distraction-v3"


class BookReacquireProgress:
    """Track declared task milestones without retaining hidden object state."""

    def __init__(
        self,
        *,
        task_name: str = "thor_book_reacquire",
        distraction_actions: tuple[str, ...] = ("RotateRight",),
        max_distraction_turns: int = 4,
        require_hidden_throughout: bool = False,
        require_hidden_at_completion: bool = False,
        distraction_stage_prefix: str | None = None,
        distraction_policy: str = "legacy-book-distraction",
    ) -> None:
        if not distraction_actions:
            raise ValueError("at least one distraction action is required")
        self.task_name = task_name
        self.distraction_actions = distraction_actions
        self.max_distraction_turns = max_distraction_turns
        self.require_hidden_throughout = require_hidden_throughout
        self.require_hidden_at_completion = require_hidden_at_completion
        self.distraction_stage_prefix = distraction_stage_prefix
        self.distraction_policy = distraction_policy
        self.initial_book_id: str | None = None
        self.initial_book_observed_step: int | None = None
        self.distraction_turns = 0
        self.distraction_transition_count = 0
        self.book_hidden_step: int | None = None
        self.book_reacquired_step: int | None = None
        self.book_picked_step: int | None = None
        self._current_book_visible = False
        self._preflight_error = ""
        self._distraction_error = ""

    @classmethod
    def phase5_k2(cls) -> "BookReacquireProgress":
        """Build the historical R1 v1 controller."""

        return cls(
            task_name="thor_book_reacquire_k2",
            distraction_actions=("RotateRight", "LookDown", "LookUp"),
            require_hidden_throughout=True,
            distraction_stage_prefix="controlled_distraction",
            distraction_policy=PHASE5_BOOK_DISTRACTION_POLICY_V1,
        )

    @classmethod
    def phase5_k2_v2(cls) -> "BookReacquireProgress":
        """Build the fixed half-turn successor without target-conditioned actions."""

        return cls(
            task_name="thor_book_reacquire_k2",
            distraction_actions=(
                "RotateRight",
                "RotateRight",
                "LookDown",
                "LookUp",
            ),
            require_hidden_throughout=False,
            require_hidden_at_completion=True,
            distraction_stage_prefix="controlled_distraction_v2",
            distraction_policy=PHASE5_BOOK_DISTRACTION_POLICY_V2,
        )

    @classmethod
    def phase5_k2_v3(cls) -> "BookReacquireProgress":
        """Build the horizon-independent half-turn plus hidden Pass successor."""

        return cls(
            task_name="thor_book_reacquire_k2",
            distraction_actions=("RotateRight", "RotateRight", "Pass"),
            require_hidden_throughout=False,
            require_hidden_at_completion=True,
            distraction_stage_prefix="controlled_distraction_v3",
            distraction_policy=PHASE5_BOOK_DISTRACTION_POLICY_V3,
        )

    @staticmethod
    def _visible_book(observation: Mapping[str, Any]) -> Mapping[str, Any] | None:
        raw_objects = observation.get("objects", [])
        if not isinstance(raw_objects, list):
            return None
        return next(
            (
                obj
                for obj in raw_objects
                if isinstance(obj, Mapping)
                and obj.get("visible") is True
                and str(obj.get("objectType", "")) == "Book"
            ),
            None,
        )

    def initialize(self, observation: Mapping[str, Any]) -> None:
        book = self._visible_book(observation)
        if book is None:
            self._preflight_error = "initial_visible_book_missing"
            return
        if not bool(book.get("pickupable", False)):
            self._preflight_error = "initial_visible_book_not_pickupable"
            return
        self.initial_book_id = str(book.get("objectId", ""))
        if not self.initial_book_id:
            self._preflight_error = "initial_visible_book_missing_object_id"
            return
        self.initial_book_observed_step = 0
        self._current_book_visible = True

    @property
    def preflight_error(self) -> str:
        return self._preflight_error

    @property
    def stage(self) -> str:
        if self._preflight_error:
            return "preflight_failed"
        if self._distraction_error:
            return "distraction_failed"
        if self.book_picked_step is not None:
            return "complete"
        if self.distraction_transition_count < len(self.distraction_actions):
            if self.distraction_turns >= self.max_distraction_turns:
                return "distraction_failed"
            if self.distraction_stage_prefix is not None:
                return (
                    f"{self.distraction_stage_prefix}_"
                    f"{self.distraction_transition_count + 1}"
                )
            if self.task_name == "thor_book_reacquire":
                return "controlled_distraction"
            return f"controlled_distraction_{self.distraction_transition_count + 1}"
        if self.book_hidden_step is None:
            return "distraction_failed"
        if self._current_book_visible:
            return "pickup_book"
        return "reacquire_book"

    def observe_before_action(self, observation: Mapping[str, Any], *, step: int) -> None:
        visible = self._visible_book(observation) is not None
        self._current_book_visible = visible
        if (
            self.initial_book_observed_step is not None
            and self.book_hidden_step is None
            and not visible
        ):
            self.book_hidden_step = int(step)
        if (
            self.book_hidden_step is not None
            and self.book_reacquired_step is None
            and visible
        ):
            self.book_reacquired_step = int(step)

    def observe_action(
        self,
        *,
        step: int,
        action: Mapping[str, Any],
        success: bool,
        observation_after: Mapping[str, Any],
    ) -> None:
        action_name = str(action.get("action", ""))
        was_distraction_action = (
            self.distraction_transition_count < len(self.distraction_actions)
        )
        if was_distraction_action:
            expected = self.distraction_actions[self.distraction_transition_count]
            if success and action_name == expected:
                self.distraction_transition_count += 1
            elif success and self.task_name != "thor_book_reacquire":
                self._distraction_error = (
                    f"unexpected_distraction_action:{action_name}:expected:{expected}"
                )
            elif not success and self.task_name != "thor_book_reacquire":
                self._distraction_error = f"distraction_action_failed:{expected}"

        if (
            success
            and self.book_hidden_step is None
            and action_name in {"RotateLeft", "RotateRight"}
        ):
            self.distraction_turns += 1

        visible = self._visible_book(observation_after) is not None
        self._current_book_visible = visible
        if self.book_hidden_step is None and not visible:
            self.book_hidden_step = int(step)
        elif (
            self.book_hidden_step is not None
            and self.book_reacquired_step is None
            and visible
        ):
            self.book_reacquired_step = int(step)

        if (
            self.require_hidden_throughout
            and was_distraction_action
            and success
            and not self._distraction_error
            and visible
        ):
            self._distraction_error = (
                f"book_visible_during_distraction:transition:"
                f"{self.distraction_transition_count}"
            )
        if (
            self.require_hidden_at_completion
            and was_distraction_action
            and self.distraction_transition_count >= len(self.distraction_actions)
            and success
            and not self._distraction_error
            and visible
        ):
            self._distraction_error = "book_visible_after_distraction"

        if (
            success
            and action_name == "PickupObject"
            and str(action.get("objectId", "")) == self.initial_book_id
        ):
            self.book_picked_step = int(step)

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(
            {
                "task_name": self.task_name,
                "distraction_policy": self.distraction_policy,
                "stage": self.stage,
                "initial_book_id": self.initial_book_id,
                "initial_book_observed_step": self.initial_book_observed_step,
                "distraction_turns": self.distraction_turns,
                "distraction_transition_count": self.distraction_transition_count,
                "required_distraction_actions": list(self.distraction_actions),
                "short_memory_k2_eviction_ready": (
                    self.distraction_transition_count >= 2
                ),
                "book_hidden_step": self.book_hidden_step,
                "book_reacquired_step": self.book_reacquired_step,
                "book_picked_step": self.book_picked_step,
                "preflight_error": self._preflight_error,
                "distraction_error": self._distraction_error,
            }
        )


class CupAfterCoffeeProgress:
    """Track the ordered CoffeeMachine-then-Cup task without spatial history."""

    task_name = "thor_cup_after_coffee_subgoal"

    def __init__(self) -> None:
        self.initial_cup_id: str | None = None
        self.initial_cup_observed_step: int | None = None
        self.cup_hidden_step: int | None = None
        self.coffee_machine_toggled_step: int | None = None
        self.cup_reacquired_step: int | None = None
        self.cup_picked_step: int | None = None
        self._current_cup_visible = False
        self._preflight_error = ""
        self._protocol_violations: list[str] = []

    @staticmethod
    def _visible_type(
        observation: Mapping[str, Any], object_type: str
    ) -> Mapping[str, Any] | None:
        raw_objects = observation.get("objects", [])
        if not isinstance(raw_objects, list):
            return None
        return next(
            (
                obj
                for obj in raw_objects
                if isinstance(obj, Mapping)
                and obj.get("visible") is True
                and str(obj.get("objectType", "")) == object_type
            ),
            None,
        )

    def initialize(self, observation: Mapping[str, Any]) -> None:
        cup = self._visible_type(observation, "Cup")
        if cup is None:
            self._preflight_error = "initial_visible_cup_missing"
            return
        if not bool(cup.get("pickupable", False)):
            self._preflight_error = "initial_visible_cup_not_pickupable"
            return
        self.initial_cup_id = str(cup.get("objectId", ""))
        if not self.initial_cup_id:
            self._preflight_error = "initial_visible_cup_missing_object_id"
            return
        self.initial_cup_observed_step = 0
        self._current_cup_visible = True

    @property
    def preflight_error(self) -> str:
        return self._preflight_error

    @property
    def stage(self) -> str:
        if self._preflight_error:
            return "preflight_failed"
        if self.cup_picked_step is not None:
            return "complete"
        if self.coffee_machine_toggled_step is None:
            return "toggle_coffee_machine"
        if self._current_cup_visible:
            return "pickup_cup"
        return "reacquire_cup"

    def observe_before_action(self, observation: Mapping[str, Any], *, step: int) -> None:
        visible = self._visible_type(observation, "Cup") is not None
        self._current_cup_visible = visible
        if (
            self.initial_cup_observed_step is not None
            and self.cup_hidden_step is None
            and not visible
        ):
            self.cup_hidden_step = int(step)
        if (
            self.cup_hidden_step is not None
            and self.cup_reacquired_step is None
            and visible
        ):
            self.cup_reacquired_step = int(step)

    def observe_action(
        self,
        *,
        step: int,
        action: Mapping[str, Any],
        success: bool,
        observation_after: Mapping[str, Any],
    ) -> None:
        action_name = str(action.get("action", ""))
        object_id = str(action.get("objectId", ""))
        visible_objects = observation_after.get("objects", [])
        by_id = (
            {
                str(obj.get("objectId", "")): obj
                for obj in visible_objects
                if isinstance(obj, Mapping) and obj.get("objectId")
            }
            if isinstance(visible_objects, list)
            else {}
        )
        target = by_id.get(object_id)
        target_type = (
            str(target.get("objectType", ""))
            if target is not None
            else object_id.split("|", 1)[0]
        )

        if success and action_name == "ToggleObjectOn" and target_type == "CoffeeMachine":
            if self.coffee_machine_toggled_step is None:
                self.coffee_machine_toggled_step = int(step)
        if success and action_name == "PickupObject" and target_type == "Cup":
            if self.coffee_machine_toggled_step is None:
                self._protocol_violations.append(
                    f"cup_picked_before_coffee_machine_at_step:{step}"
                )
            if self.cup_picked_step is None:
                self.cup_picked_step = int(step)

        visible = self._visible_type(observation_after, "Cup") is not None
        self._current_cup_visible = visible
        if self.cup_hidden_step is None and not visible:
            self.cup_hidden_step = int(step)
        elif (
            self.cup_hidden_step is not None
            and self.cup_reacquired_step is None
            and visible
        ):
            self.cup_reacquired_step = int(step)

    def snapshot(self) -> dict[str, Any]:
        ordered = (
            self.coffee_machine_toggled_step is not None
            and self.cup_picked_step is not None
            and self.coffee_machine_toggled_step < self.cup_picked_step
            and not self._protocol_violations
        )
        return deepcopy(
            {
                "task_name": self.task_name,
                "stage": self.stage,
                "initial_cup_id": self.initial_cup_id,
                "initial_cup_observed_step": self.initial_cup_observed_step,
                "cup_hidden_step": self.cup_hidden_step,
                "coffee_machine_toggled_step": self.coffee_machine_toggled_step,
                "cup_reacquired_step": self.cup_reacquired_step,
                "cup_picked_step": self.cup_picked_step,
                "ordered_subgoal_passed": (
                    ordered if self.cup_picked_step is not None else None
                ),
                "protocol_violations": list(self._protocol_violations),
                "preflight_error": self._preflight_error,
            }
        )

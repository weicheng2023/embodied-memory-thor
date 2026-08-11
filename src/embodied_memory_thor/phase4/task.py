"""Planner-safe progress state for the controlled real Book task."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


class BookReacquireProgress:
    """Track declared task milestones without retaining hidden object state."""

    def __init__(
        self,
        *,
        task_name: str = "thor_book_reacquire",
        distraction_actions: tuple[str, ...] = ("RotateRight",),
        max_distraction_turns: int = 4,
        require_hidden_throughout: bool = False,
    ) -> None:
        if not distraction_actions:
            raise ValueError("at least one distraction action is required")
        self.task_name = task_name
        self.distraction_actions = distraction_actions
        self.max_distraction_turns = max_distraction_turns
        self.require_hidden_throughout = require_hidden_throughout
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
        """Build the frozen R1 controller that evicts observation 0 from K=2."""

        return cls(
            task_name="thor_book_reacquire_k2",
            distraction_actions=("RotateRight", "LookDown", "LookUp"),
            require_hidden_throughout=True,
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
            success
            and action_name == "PickupObject"
            and str(action.get("objectId", "")) == self.initial_book_id
        ):
            self.book_picked_step = int(step)

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(
            {
                "task_name": self.task_name,
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

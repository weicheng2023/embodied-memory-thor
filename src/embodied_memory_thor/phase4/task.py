"""Planner-safe progress state for the controlled real Book task."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


class BookReacquireProgress:
    """Track declared task milestones without retaining hidden object state."""

    def __init__(self, *, max_distraction_turns: int = 4) -> None:
        self.max_distraction_turns = max_distraction_turns
        self.initial_book_id: str | None = None
        self.initial_book_observed_step: int | None = None
        self.distraction_turns = 0
        self.book_hidden_step: int | None = None
        self.book_reacquired_step: int | None = None
        self.book_picked_step: int | None = None
        self._current_book_visible = False
        self._preflight_error = ""

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
        if self.book_picked_step is not None:
            return "complete"
        if self.book_hidden_step is None:
            if self.distraction_turns >= self.max_distraction_turns:
                return "distraction_failed"
            return "controlled_distraction"
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
        if (
            success
            and self.book_hidden_step is None
            and str(action.get("action", "")) in {"RotateLeft", "RotateRight"}
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
            success
            and str(action.get("action", "")) == "PickupObject"
            and str(action.get("objectId", "")) == self.initial_book_id
        ):
            self.book_picked_step = int(step)

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(
            {
                "task_name": "thor_book_reacquire",
                "stage": self.stage,
                "initial_book_id": self.initial_book_id,
                "initial_book_observed_step": self.initial_book_observed_step,
                "distraction_turns": self.distraction_turns,
                "book_hidden_step": self.book_hidden_step,
                "book_reacquired_step": self.book_reacquired_step,
                "book_picked_step": self.book_picked_step,
                "preflight_error": self._preflight_error,
            }
        )

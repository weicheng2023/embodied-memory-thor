"""Lazy, failure-aware adapter around the optional AI2-THOR Controller."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from embodied_memory_thor.env.base import EmbodiedEnv


class ThorEnv(EmbodiedEnv):
    """Expose AI2-THOR through the small environment contract.

    Import and controller construction are delayed until ``reset`` so the
    package and all mock-mode tools remain usable without AI2-THOR installed.
    A controller-like object may be injected for unit or integration tests.
    """

    def __init__(
        self,
        *,
        controller: Any | None = None,
        controller_kwargs: Mapping[str, Any] | None = None,
    ) -> None:
        self._controller = controller
        self._controller_kwargs = dict(controller_kwargs or {})
        self._last_event: Any | None = getattr(controller, "last_event", None)

    @property
    def last_event(self) -> Any:
        """Return the latest AI2-THOR event."""

        if self._last_event is None:
            raise RuntimeError("ThorEnv has no event; call reset(scene) first")
        return self._last_event

    def reset(self, scene: str) -> Any:
        """Start or reset AI2-THOR to the requested scene."""

        if not scene:
            raise ValueError("scene must be a non-empty AI2-THOR scene name")

        if self._controller is None:
            try:
                from ai2thor.controller import Controller
            except (ImportError, ModuleNotFoundError) as exc:
                raise RuntimeError(
                    "AI2-THOR is not installed. Install the 'thor' extra or use MockEnv."
                ) from exc

            options = dict(self._controller_kwargs)
            options.setdefault("scene", scene)
            try:
                self._controller = Controller(**options)
                self._last_event = self._controller.last_event
            except Exception as exc:
                self._controller = None
                raise RuntimeError(
                    "AI2-THOR could not start. Check Unity/display support or use MockEnv. "
                    f"Underlying error: {type(exc).__name__}: {exc}"
                ) from exc
        else:
            try:
                self._last_event = self._controller.reset(scene=scene)
            except Exception as exc:
                raise RuntimeError(
                    f"AI2-THOR could not reset scene {scene!r}: {type(exc).__name__}: {exc}"
                ) from exc

        return self.last_event

    def step(self, action_dict: Mapping[str, Any]) -> Any:
        """Execute a structured AI2-THOR action."""

        if self._controller is None:
            raise RuntimeError("ThorEnv is not initialized; call reset(scene) first")
        if not isinstance(action_dict, Mapping):
            raise TypeError("action_dict must be a mapping")
        if not str(action_dict.get("action", "")).strip():
            raise ValueError("action_dict must include a non-empty 'action'")

        try:
            self._last_event = self._controller.step(**dict(action_dict))
        except Exception as exc:
            raise RuntimeError(
                f"AI2-THOR action failed before producing an event: {type(exc).__name__}: {exc}"
            ) from exc
        return self._last_event

    def get_visible_objects(self) -> list[dict[str, Any]]:
        """Return raw metadata for objects marked visible by AI2-THOR."""

        return [obj for obj in self.get_all_objects() if bool(obj.get("visible", False))]

    def get_all_objects(self) -> list[dict[str, Any]]:
        """Return defensive copies of all current AI2-THOR object records."""

        objects = self._metadata().get("objects", [])
        if not isinstance(objects, list):
            return []
        return [deepcopy(item) for item in objects if isinstance(item, dict)]

    def get_agent_state(self) -> dict[str, Any]:
        """Return a defensive copy of current agent metadata."""

        agent = self._metadata().get("agent", {})
        return deepcopy(agent) if isinstance(agent, dict) else {}

    def save_frame(self, path: str | Path) -> Path:
        """Save the latest RGB frame using Pillow when available."""

        frame = getattr(self.last_event, "frame", None)
        if frame is None:
            raise RuntimeError("the current AI2-THOR event does not contain an RGB frame")

        try:
            from PIL import Image
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError("Pillow is required to save AI2-THOR frames") from exc

        output_path = Path(path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(frame).save(output_path)
        return output_path

    def close(self) -> None:
        """Stop the Unity controller if it was created."""

        if self._controller is not None:
            stop = getattr(self._controller, "stop", None)
            if callable(stop):
                stop()
        self._controller = None
        self._last_event = None

    def _metadata(self) -> Mapping[str, Any]:
        metadata = getattr(self.last_event, "metadata", None)
        return metadata if isinstance(metadata, Mapping) else {}

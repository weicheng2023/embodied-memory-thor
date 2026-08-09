"""Common interface implemented by real and mock embodied environments."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Mapping


class EmbodiedEnv(ABC):
    """Minimal environment contract used by later agent phases."""

    @abstractmethod
    def reset(self, scene: str) -> Any:
        """Reset the environment to ``scene`` and return its current event."""

    @abstractmethod
    def step(self, action_dict: Mapping[str, Any]) -> Any:
        """Execute one structured action and return the resulting event."""

    @abstractmethod
    def get_visible_objects(self) -> list[dict[str, Any]]:
        """Return raw metadata for currently visible objects."""

    @abstractmethod
    def get_all_objects(self) -> list[dict[str, Any]]:
        """Return raw metadata for all scene objects."""

    @abstractmethod
    def get_agent_state(self) -> dict[str, Any]:
        """Return the current agent metadata."""

    @abstractmethod
    def save_frame(self, path: str | Path) -> Path:
        """Save the current RGB frame and return the resolved output path."""

    def close(self) -> None:
        """Release resources, if any."""

    def __enter__(self) -> "EmbodiedEnv":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

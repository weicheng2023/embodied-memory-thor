"""JSONL step logging and JSON episode summaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from embodied_memory_thor.utils.serialization import to_jsonable


def create_episode_dir(
    *,
    task_name: str,
    planner_name: str,
    mode: str,
    root: str | Path = "outputs/runs",
) -> Path:
    """Create a timestamped, collision-resistant episode output directory."""

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    path = Path(root) / timestamp / f"{task_name}__{planner_name}__{mode}"
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve()


class EpisodeLogger:
    """Write one JSON object per step plus a final summary."""

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.episode_path = self.output_dir / "episode.jsonl"
        self.summary_path = self.output_dir / "summary.json"
        self.episode_path.write_text("", encoding="utf-8")

    def log_step(self, record: Mapping[str, Any]) -> None:
        """Append one JSON-safe step record."""

        payload = json.dumps(to_jsonable(record), ensure_ascii=False, sort_keys=True)
        with self.episode_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.write("\n")

    def write_summary(self, summary: Mapping[str, Any]) -> None:
        """Write the final episode summary atomically enough for local runs."""

        payload = json.dumps(to_jsonable(summary), ensure_ascii=False, indent=2, sort_keys=True)
        self.summary_path.write_text(payload + "\n", encoding="utf-8")

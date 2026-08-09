"""Validated loading of embodied task definitions from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


DEFAULT_TASKS_PATH = Path(__file__).resolve().parents[3] / "configs" / "tasks.yaml"


@dataclass(frozen=True)
class TaskDefinition:
    """Validated task configuration used by planners and evaluators."""

    task_name: str
    natural_language_instruction: str
    required_objects: tuple[str, ...]
    goal_conditions: tuple[dict[str, Any], ...]
    max_steps: int


def load_tasks(path: str | Path | None = None) -> dict[str, TaskDefinition]:
    """Load and validate every task in a YAML configuration file."""

    try:
        import yaml
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError("PyYAML is required to load task configuration") from exc

    config_path = Path(path) if path is not None else DEFAULT_TASKS_PATH
    if not config_path.is_file():
        raise FileNotFoundError(f"task configuration not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, Mapping) or not isinstance(document.get("tasks"), Mapping):
        raise ValueError("task configuration must contain a 'tasks' mapping")

    tasks: dict[str, TaskDefinition] = {}
    for key, raw_task in document["tasks"].items():
        if not isinstance(key, str) or not isinstance(raw_task, Mapping):
            raise ValueError("each task entry must map a string name to a mapping")
        task = _parse_task(key, raw_task)
        if task.task_name in tasks:
            raise ValueError(f"duplicate task_name: {task.task_name}")
        tasks[task.task_name] = task
    return tasks


def load_task(task_name: str, path: str | Path | None = None) -> TaskDefinition:
    """Load one named task or raise an actionable error."""

    tasks = load_tasks(path)
    try:
        return tasks[task_name]
    except KeyError as exc:
        choices = ", ".join(sorted(tasks))
        raise KeyError(f"unknown task {task_name!r}; available tasks: {choices}") from exc


def _parse_task(key: str, raw_task: Mapping[str, Any]) -> TaskDefinition:
    required_fields = (
        "task_name",
        "natural_language_instruction",
        "required_objects",
        "goal_conditions",
        "max_steps",
    )
    missing_fields = [field for field in required_fields if field not in raw_task]
    if missing_fields:
        raise ValueError(f"task {key!r} is missing fields: {', '.join(missing_fields)}")

    task_name = str(raw_task["task_name"]).strip()
    instruction = str(raw_task["natural_language_instruction"]).strip()
    required_objects = raw_task["required_objects"]
    goal_conditions = raw_task["goal_conditions"]
    max_steps = raw_task["max_steps"]

    if task_name != key:
        raise ValueError(f"task key {key!r} does not match task_name {task_name!r}")
    if not instruction:
        raise ValueError(f"task {key!r} has an empty natural_language_instruction")
    if not isinstance(required_objects, list) or not all(
        isinstance(item, str) and item.strip() for item in required_objects
    ):
        raise ValueError(f"task {key!r} required_objects must be a non-empty string list")
    if not required_objects:
        raise ValueError(f"task {key!r} required_objects cannot be empty")
    if not isinstance(goal_conditions, list) or not goal_conditions or not all(
        isinstance(item, Mapping) for item in goal_conditions
    ):
        raise ValueError(f"task {key!r} goal_conditions must be a non-empty mapping list")
    if not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps <= 0:
        raise ValueError(f"task {key!r} max_steps must be a positive integer")

    return TaskDefinition(
        task_name=task_name,
        natural_language_instruction=instruction,
        required_objects=tuple(item.strip() for item in required_objects),
        goal_conditions=tuple(dict(item) for item in goal_conditions),
        max_steps=max_steps,
    )

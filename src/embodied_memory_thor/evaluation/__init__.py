"""Task definitions, availability checks, and state-based evaluation."""

from embodied_memory_thor.evaluation.object_availability import (
    AvailabilityResult,
    check_object_availability,
)
from embodied_memory_thor.evaluation.success_checker import (
    SuccessResult,
    evaluate_task_success,
)
from embodied_memory_thor.evaluation.task_loader import TaskDefinition, load_task, load_tasks
from embodied_memory_thor.evaluation.task_progress import TaskProgressTracker
from embodied_memory_thor.evaluation.phase3_protocol import (
    CONDITIONS,
    LAYOUT_SEEDS,
    PROTOCOL_VERSION,
    SHORT_TERM_CAPACITY,
    VARIANT_PLANNERS,
    add_matched_deltas,
    aggregate_results,
    build_protocol_manifest,
    evaluate_acceptance,
)

__all__ = [
    "AvailabilityResult",
    "SuccessResult",
    "TaskDefinition",
    "TaskProgressTracker",
    "CONDITIONS",
    "LAYOUT_SEEDS",
    "PROTOCOL_VERSION",
    "SHORT_TERM_CAPACITY",
    "VARIANT_PLANNERS",
    "add_matched_deltas",
    "aggregate_results",
    "build_protocol_manifest",
    "evaluate_acceptance",
    "check_object_availability",
    "evaluate_task_success",
    "load_task",
    "load_tasks",
]

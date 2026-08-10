"""Phase 4 real-AI2-THOR execution and auditable-trace components."""

from embodied_memory_thor.phase4.contracts import (
    EVALUATOR_ONLY_LABEL,
    PlannerDecision,
    PlannerRequest,
    RGB_BOUNDARY_LABEL,
    audit_planner_request,
    build_planner_observation,
)
from embodied_memory_thor.phase4.spatial_memory import (
    NoThorMemory,
    ThorObjectMemory,
    ThorObjectMemoryRecord,
    build_thor_memory,
)
from embodied_memory_thor.phase4.planners import (
    OpenAICompatiblePlanner,
    ThorBookReacquirePlanner,
    validate_planner_decision,
)
from embodied_memory_thor.phase4.parity import compare_trace_parity
from embodied_memory_thor.phase4.runner import ThorEpisodeConfig, ThorEpisodeRunner
from embodied_memory_thor.phase4.task import BookReacquireProgress

__all__ = [
    "BookReacquireProgress",
    "EVALUATOR_ONLY_LABEL",
    "NoThorMemory",
    "OpenAICompatiblePlanner",
    "PlannerDecision",
    "PlannerRequest",
    "RGB_BOUNDARY_LABEL",
    "ThorObjectMemory",
    "ThorObjectMemoryRecord",
    "ThorBookReacquirePlanner",
    "ThorEpisodeConfig",
    "ThorEpisodeRunner",
    "audit_planner_request",
    "build_planner_observation",
    "build_thor_memory",
    "compare_trace_parity",
    "validate_planner_decision",
]

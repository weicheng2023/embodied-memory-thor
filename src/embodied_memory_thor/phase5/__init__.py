"""Phase 5 comparison infrastructure kept separate from accepted Phase 4 tasks."""

from embodied_memory_thor.phase5.interventions import EvaluatorIntervention

__all__ = ["EvaluatorIntervention"]
from .protocol import (
    PHASE5_METRIC_SCHEMA_VERSION,
    PHASE5_PROTOCOL_VERSION,
    PHASE5_REQUIRED_METRICS,
    QualificationRecord,
    build_formal_manifest,
    select_first_passing,
    validate_formal_manifest,
)

__all__ = [
    "PHASE5_METRIC_SCHEMA_VERSION",
    "PHASE5_PROTOCOL_VERSION",
    "PHASE5_REQUIRED_METRICS",
    "QualificationRecord",
    "build_formal_manifest",
    "select_first_passing",
    "validate_formal_manifest",
]

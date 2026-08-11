"""Phase 5 comparison and qualification infrastructure."""

from .anchors import (
    ANCHOR_QUALIFICATION_VERSION,
    ANCHOR_REGISTRY_VERSION,
    build_geometry_candidate_plan,
    build_target_independent_coverage_route,
    public_anchor_reference,
)
from .interventions import EvaluatorIntervention
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
    "ANCHOR_QUALIFICATION_VERSION",
    "ANCHOR_REGISTRY_VERSION",
    "EvaluatorIntervention",
    "PHASE5_METRIC_SCHEMA_VERSION",
    "PHASE5_PROTOCOL_VERSION",
    "PHASE5_REQUIRED_METRICS",
    "QualificationRecord",
    "build_geometry_candidate_plan",
    "build_target_independent_coverage_route",
    "build_formal_manifest",
    "public_anchor_reference",
    "select_first_passing",
    "validate_formal_manifest",
]

"""Phase-7B parameterized recent-observation memory without Phase-5 rewrites."""

from __future__ import annotations

from dataclasses import replace

from embodied_memory_thor.phase4.spatial_memory import (
    NoThorMemory,
    ThorMemoryProvider,
    ThorObjectMemory,
    ThorShortMemory,
)
from embodied_memory_thor.phase4.runner import ThorEpisodeConfig


PHASE7B_RECENT_MEMORY_VERSION = "phase7b-recent-observation-memory-v1"
PHASE7B_VARIANTS = (
    "no_memory",
    "recent_memory_k2",
    "recent_memory_k4",
    "recent_memory_k8",
    "object_memory",
)
PHASE7B_RECENT_CAPACITIES = {
    "recent_memory_k2": 2,
    "recent_memory_k4": 4,
    "recent_memory_k8": 8,
}


class RecentObservationMemory(ThorShortMemory):
    """Phase-7B name for the existing exact last-K observation semantics.

    This additive subclass intentionally does not override observation,
    retrieval, or snapshot behavior. In particular, K=2 remains byte-for-byte
    compatible on deterministic fixtures with the historical
    :class:`ThorShortMemory(k=2)` path; Phase 5 continues to construct its own
    provider through ``build_thor_memory('short_memory_k2')``.
    """

    provider_version = PHASE7B_RECENT_MEMORY_VERSION

    def __init__(self, k: int) -> None:
        super().__init__(k=k)


class Phase7BThorEpisodeConfig(ThorEpisodeConfig):
    """Accept Phase-7B labels without changing the protected Phase-4 config."""

    def validate(self) -> None:
        if self.memory not in PHASE7B_VARIANTS:
            raise ValueError(f"unsupported Phase7B memory variant: {self.memory}")
        validation_label = (
            "short_memory_k2"
            if recent_capacity(self.memory) is not None
            else self.memory
        )
        historical_shape = replace(self, memory=validation_label)
        ThorEpisodeConfig.validate(historical_shape)


def recent_capacity(variant: str) -> int | None:
    """Return the frozen observation capacity for a Phase-7B variant."""

    return PHASE7B_RECENT_CAPACITIES.get(str(variant))


def build_phase7b_memory(variant: str) -> ThorMemoryProvider:
    """Construct exactly one frozen Phase-7B memory condition."""

    capacity = recent_capacity(variant)
    if capacity is not None:
        return RecentObservationMemory(capacity)
    if variant == "no_memory":
        return NoThorMemory()
    if variant == "object_memory":
        return ThorObjectMemory()
    raise ValueError(f"unsupported Phase7B memory variant: {variant}")

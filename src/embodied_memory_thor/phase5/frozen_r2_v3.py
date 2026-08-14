"""Load the conservative six-configuration Phase 5 R2 runtime set v3."""

from __future__ import annotations

from pathlib import Path

from .frozen_r2 import FrozenR2Runtime, load_frozen_r2_runtime


PROJECT_ROOT = Path(__file__).resolve().parents[3]
R2_RUNTIME_SET_VERSION_V3 = "phase5-r2-frozen-runtime-set-v3"
DEFAULT_PUBLIC_SET_PATH_V3 = PROJECT_ROOT / "configs" / "phase5_r2_frozen_runtime_v3.json"
DEFAULT_PRIVATE_SET_PATH_V3 = (
    PROJECT_ROOT / "outputs" / "phase5_r2_frozen_runtime_v3"
    / "evaluator_only_configuration_registry.json"
)
DEFAULT_SEARCH_ROUTES_PATH_V3 = PROJECT_ROOT / "configs" / "phase5_r2_search_routes_v3.json"


def load_frozen_r2_runtime_v3(configuration_id: str) -> FrozenR2Runtime:
    """Join one public v3 route contract to ignored evaluator-only start data."""

    return load_frozen_r2_runtime(
        configuration_id,
        public_set_path=DEFAULT_PUBLIC_SET_PATH_V3,
        private_set_path=DEFAULT_PRIVATE_SET_PATH_V3,
        search_routes_path=DEFAULT_SEARCH_ROUTES_PATH_V3,
        expected_runtime_set_version=R2_RUNTIME_SET_VERSION_V3,
    )

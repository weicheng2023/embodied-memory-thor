"""Load the six-configuration Phase 5 R2 frozen runtime set v2."""

from __future__ import annotations

from pathlib import Path

from .frozen_r2 import FrozenR2Runtime, load_frozen_r2_runtime


PROJECT_ROOT = Path(__file__).resolve().parents[3]
R2_RUNTIME_SET_VERSION_V2 = "phase5-r2-frozen-runtime-set-v2"
DEFAULT_PUBLIC_SET_PATH_V2 = PROJECT_ROOT / "configs" / "phase5_r2_frozen_runtime_v2.json"
DEFAULT_PRIVATE_SET_PATH_V2 = (
    PROJECT_ROOT / "outputs" / "phase5_r2_frozen_runtime_v2"
    / "evaluator_only_configuration_registry.json"
)
DEFAULT_SEARCH_ROUTES_PATH_V2 = PROJECT_ROOT / "configs" / "phase5_r2_search_routes_v2.json"


def load_frozen_r2_runtime_v2(configuration_id: str) -> FrozenR2Runtime:
    """Join one public v2 route contract to ignored evaluator-only start data."""

    return load_frozen_r2_runtime(
        configuration_id,
        public_set_path=DEFAULT_PUBLIC_SET_PATH_V2,
        private_set_path=DEFAULT_PRIVATE_SET_PATH_V2,
        search_routes_path=DEFAULT_SEARCH_ROUTES_PATH_V2,
        expected_runtime_set_version=R2_RUNTIME_SET_VERSION_V2,
    )

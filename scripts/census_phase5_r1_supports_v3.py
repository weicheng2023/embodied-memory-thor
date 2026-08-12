#!/usr/bin/env python3
"""Run the qualification-aligned Phase 5 R1 support census v3."""

from pathlib import Path

from census_phase5_r1_supports_v2 import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    raise SystemExit(
        main(
            default_config=(
                PROJECT_ROOT / "configs" / "phase5_r1_support_census_v3.json"
            )
        )
    )

#!/usr/bin/env python3
"""Run one non-formal Phase-7A configuration with saved RGB presentation frames."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase4.runner import ThorEpisodeConfig, ThorEpisodeRunner  # noqa: E402
from embodied_memory_thor.phase4.task import PHASE5_BOOK_DISTRACTION_POLICY_V4  # noqa: E402
from embodied_memory_thor.phase7.holdout import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    load_phase7a_holdout_runtime,
)


DEFAULT_CONFIGURATION = "FloorPlan308_Phase7A_R1_holdout_001"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "readme_presentation_source"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration-id", default=DEFAULT_CONFIGURATION)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    parser.add_argument("--max-steps", type=int, default=72)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.width <= 0 or args.height <= 0 or args.max_steps <= 0:
        raise ValueError("width, height, and max-steps must be positive")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    runtime = load_phase7a_holdout_runtime(
        args.configuration_id,
        manifest_path=args.manifest,
        private_registry_path=PROJECT_ROOT / str(manifest["evaluator_registry"]),
        route_registry_path=PROJECT_ROOT / str(manifest["route_registry"]),
    )
    controller_settings = deepcopy(dict(manifest["controller_settings"]))
    controller_settings.update({"width": args.width, "height": args.height})
    config = ThorEpisodeConfig(
        task="thor_book_reacquire_k2",
        scene=runtime.configuration.scene,
        planner="deterministic",
        memory="object_memory",
        book_distraction_policy=PHASE5_BOOK_DISTRACTION_POLICY_V4,
        search_route_id=runtime.search_route.route_id,
        condition="stable",
        mode="debug",
        max_steps=args.max_steps,
        output_dir=args.output_dir.resolve(),
        save_frames=True,
        trace_html=True,
        visualize=False,
        save_evaluator_debug=False,
        included_in_formal_aggregate=False,
        run_purpose="readme_presentation_replay_v1",
        controller_settings=controller_settings,
    )
    config.validate()
    summary = ThorEpisodeRunner(
        config,
        search_route=runtime.search_route,
        evaluator_setup=runtime.configuration,
    ).run()
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

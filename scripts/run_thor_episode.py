#!/usr/bin/env python3
"""Run one Phase 4 real AI2-THOR episode in formal or debug mode."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase4.runner import (  # noqa: E402
    ThorEpisodeConfig,
    ThorEpisodeRunner,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the controlled real-THOR Book reacquisition episode with an "
            "auditable planner-safe trace."
        )
    )
    parser.add_argument("--task", default="thor_book_reacquire")
    parser.add_argument("--scene", default="FloorPlan1")
    parser.add_argument(
        "--planner",
        choices=("object_memory", "no_memory", "deterministic", "openai_compatible"),
        default="object_memory",
        help=(
            "object_memory/no_memory select the deterministic reference planner "
            "with that history boundary"
        ),
    )
    parser.add_argument(
        "--memory",
        choices=("object_memory", "no_memory"),
        help="explicit memory mode; mainly used with deterministic/openai_compatible",
    )
    parser.add_argument("--mode", choices=("formal", "debug"), default="formal")
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--output-dir")
    parser.add_argument("--save-frames", action="store_true")
    parser.add_argument("--trace-html", action="store_true")
    parser.add_argument("--visualize", action="store_true")
    parser.add_argument("--step-delay", type=float, default=0.0)
    parser.add_argument(
        "--save-evaluator-debug",
        action="store_true",
        help=(
            "write a separate EVALUATOR ONLY file; never adds full metadata to planner input"
        ),
    )
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-5.6"))
    parser.add_argument("--base-url", help="optional OpenAI-compatible API base URL")
    parser.add_argument("--width", type=int, default=300)
    parser.add_argument("--height", type=int, default=300)
    parser.add_argument("--quality", default="Low")
    parser.add_argument("--grid-size", type=float, default=0.25)
    parser.add_argument("--rotate-step-degrees", type=int, default=90)
    return parser


def _planner_and_memory(args: argparse.Namespace) -> tuple[str, str]:
    if args.planner == "object_memory":
        if args.memory and args.memory != "object_memory":
            raise ValueError("--planner object_memory conflicts with --memory no_memory")
        return "deterministic", "object_memory"
    if args.planner == "no_memory":
        if args.memory and args.memory != "no_memory":
            raise ValueError("--planner no_memory conflicts with --memory object_memory")
        return "deterministic", "no_memory"
    return args.planner, args.memory or "object_memory"


def _build_config(args: argparse.Namespace) -> ThorEpisodeConfig:
    planner, memory = _planner_and_memory(args)
    if args.width <= 0 or args.height <= 0:
        raise ValueError("width and height must be positive")
    if args.grid_size <= 0 or args.rotate_step_degrees <= 0:
        raise ValueError("grid size and rotate-step-degrees must be positive")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None
    return ThorEpisodeConfig(
        task=args.task,
        scene=args.scene,
        planner=planner,
        memory=memory,
        mode=args.mode,
        max_steps=args.max_steps,
        output_dir=output_dir,
        save_frames=args.save_frames,
        trace_html=args.trace_html,
        visualize=args.visualize,
        step_delay=args.step_delay,
        save_evaluator_debug=args.save_evaluator_debug,
        model=args.model,
        base_url=args.base_url,
        controller_settings={
            "width": args.width,
            "height": args.height,
            "quality": args.quality,
            "gridSize": args.grid_size,
            "snapToGrid": True,
            "rotateStepDegrees": args.rotate_step_degrees,
            "fieldOfView": 90,
            "renderDepthImage": False,
            "renderInstanceSegmentation": False,
        },
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = _build_config(args)
        config.validate()
    except ValueError as exc:
        print(f"configuration_error: {exc}", file=sys.stderr)
        return 2

    summary = ThorEpisodeRunner(config).run()
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

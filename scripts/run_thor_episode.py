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
from embodied_memory_thor.phase5.frozen_r1 import (  # noqa: E402
    FrozenR1ConfigurationError,
    load_frozen_r1_runtime,
)
from embodied_memory_thor.phase5.frozen_r2 import (  # noqa: E402
    FrozenR2ConfigurationError,
    load_frozen_r2_runtime,
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
        "--configuration-id",
        help=(
            "opaque frozen R1 or R2 configuration; loads evaluator-only setup "
            "and public action-only routes"
        ),
    )
    parser.add_argument(
        "--planner",
        choices=(
            "object_memory",
            "short_memory_k2",
            "no_memory",
            "deterministic",
            "openai_compatible",
        ),
        default="object_memory",
        help=(
            "object_memory/short_memory_k2/no_memory select the deterministic reference planner "
            "with that history boundary"
        ),
    )
    parser.add_argument(
        "--memory",
        choices=("object_memory", "short_memory_k2", "no_memory"),
        help="explicit memory mode; mainly used with deterministic/openai_compatible",
    )
    parser.add_argument(
        "--subgoal-route-id",
        help="public ordered-R2 task-subgoal navigation route ID",
    )
    parser.add_argument(
        "--search-route-id",
        help=(
            "public target-independent Phase 5 fallback route ID"
        ),
    )
    parser.add_argument("--mode", choices=("formal", "debug"), default="formal")
    parser.add_argument(
        "--condition",
        choices=("stable", "stale_r1"),
        default="stable",
    )
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--output-dir")
    parser.add_argument("--save-frames", action="store_true")
    parser.add_argument("--trace-html", action="store_true")
    parser.add_argument(
        "--visualize",
        action="store_true",
        help=(
            "request the crash-isolated OpenCV debug viewer; GUI/Qt failure is "
            "logged and the episode continues, so pair with --save-frames for fallback"
        ),
    )
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
    memory_aliases = {"object_memory", "short_memory_k2", "no_memory"}
    if args.planner in memory_aliases:
        if args.memory and args.memory != args.planner:
            raise ValueError(
                f"--planner {args.planner} conflicts with --memory {args.memory}"
            )
        return "deterministic", args.planner
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
        subgoal_route_id=args.subgoal_route_id,
        search_route_id=args.search_route_id,
        condition=args.condition,
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
        r1_runtime = None
        r2_runtime = None
        if args.configuration_id:
            if args.task == "thor_book_reacquire_k2":
                r1_runtime = load_frozen_r1_runtime(args.configuration_id)
                runtime = r1_runtime
            elif args.task == "thor_cup_after_coffee_subgoal":
                r2_runtime = load_frozen_r2_runtime(args.configuration_id)
                runtime = r2_runtime
            else:
                raise ValueError(
                    "--configuration-id requires a Phase 5 comparison task"
                )
            if args.scene != "FloorPlan1" and args.scene != runtime.configuration.scene:
                raise ValueError("--scene conflicts with the frozen configuration")
            args.scene = runtime.configuration.scene
            frozen_search_route = (
                r1_runtime.search_route
                if r1_runtime is not None
                else r2_runtime.fallback_route
            )
            if args.search_route_id and args.search_route_id != frozen_search_route.route_id:
                raise ValueError("--search-route-id conflicts with the frozen configuration")
            args.search_route_id = frozen_search_route.route_id
            if r2_runtime is not None:
                if (
                    args.subgoal_route_id
                    and args.subgoal_route_id != r2_runtime.subgoal_route.route_id
                ):
                    raise ValueError(
                        "--subgoal-route-id conflicts with the frozen configuration"
                    )
                args.subgoal_route_id = r2_runtime.subgoal_route.route_id
            elif args.subgoal_route_id:
                raise ValueError("--subgoal-route-id requires an ordered-R2 configuration")
        config = _build_config(args)
        config.validate()
    except (
        FrozenR1ConfigurationError,
        FrozenR2ConfigurationError,
        OSError,
        ValueError,
    ) as exc:
        print(f"configuration_error: {exc}", file=sys.stderr)
        return 2

    summary = ThorEpisodeRunner(
        config,
        search_route=(
            r1_runtime.search_route
            if r1_runtime is not None
            else r2_runtime.fallback_route if r2_runtime is not None else None
        ),
        subgoal_route=(r2_runtime.subgoal_route if r2_runtime is not None else None),
        evaluator_setup=(
            r1_runtime.configuration
            if r1_runtime is not None
            else r2_runtime.configuration if r2_runtime is not None else None
        ),
        intervention=(
            r1_runtime.intervention()
            if r1_runtime is not None and config.condition == "stale_r1"
            else None
        ),
    ).run()
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

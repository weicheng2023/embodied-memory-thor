#!/usr/bin/env python3
"""List normalized objects from a real or mock embodied scene."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env import MockEnv, ThorEnv  # noqa: E402
from embodied_memory_thor.env.object_parser import parse_objects  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """Build command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Inspect AI2-THOR-style object metadata without assuming optional fields exist."
    )
    parser.add_argument(
        "--scene",
        help="scene name (defaults to MockKitchen in mock mode or FloorPlan1 otherwise)",
    )
    parser.add_argument("--mock", action="store_true", help="use the deterministic mock kitchen")
    parser.add_argument(
        "--partial-observability",
        action="store_true",
        help="show only the current seeded mock view",
    )
    parser.add_argument("--seed", type=int, default=0, help="partial mock layout seed")
    parser.add_argument("--visible-only", action="store_true", help="print only visible objects")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def _compact_object(obj: dict[str, Any]) -> str:
    parents = ", ".join(obj["parentReceptacles"]) or "-"
    flags = [
        name
        for name in ("pickupable", "receptacle", "openable", "toggleable", "sliceable")
        if obj[name]
    ]
    return (
        f"- {obj['objectType']:<12} {obj['objectId']:<20} "
        f"visible={str(obj['visible']):<5} parents={parents:<18} flags={','.join(flags) or '-'}"
    )


def main(argv: list[str] | None = None) -> int:
    """Reset the selected environment and print its normalized objects."""

    args = build_parser().parse_args(argv)
    if args.partial_observability and not args.mock:
        print("--partial-observability currently requires --mock", file=sys.stderr)
        return 2
    scene = args.scene or (MockEnv.DEFAULT_SCENE if args.mock else "FloorPlan1")
    env = (
        MockEnv(partial_observability=args.partial_observability, layout_seed=args.seed)
        if args.mock
        else ThorEnv()
    )

    try:
        event = env.reset(scene)
        all_objects = parse_objects(event)
        visible_objects = parse_objects(event, visible_only=True)
        evaluator_object_count = len(parse_objects(env.get_evaluator_state()))
        selected = visible_objects if args.visible_only else all_objects

        if args.json:
            print(
                json.dumps(
                    {
                        "mode": (
                            "mock_partial"
                            if args.partial_observability
                            else ("mock" if args.mock else "ai2thor")
                        ),
                        "scene": scene,
                        "partial_observability": args.partial_observability,
                        "layout_seed": args.seed if args.partial_observability else None,
                        "observation_object_count": len(all_objects),
                        "evaluator_object_count": evaluator_object_count,
                        "visible_object_count": len(visible_objects),
                        "objects": selected,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            mode = "mock_partial" if args.partial_observability else ("mock" if args.mock else "ai2thor")
            print(f"Mode: {mode}")
            print(f"Scene: {scene}")
            print(f"Observed objects: {len(all_objects)} ({len(visible_objects)} visible)")
            print("")
            for obj in selected:
                print(_compact_object(obj))
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"Environment unavailable: {exc}", file=sys.stderr)
        return 2
    finally:
        env.close()


if __name__ == "__main__":
    raise SystemExit(main())

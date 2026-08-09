#!/usr/bin/env python3
"""Inspect optional Embodied-Memory-THOR runtime capabilities safely."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.utils.environment import (  # noqa: E402
    collect_environment_report,
    format_human_report,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Check Python, AI2-THOR, credential, and display hints without "
            "starting Unity or making network calls."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of human-readable text",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return exit code 1 unless every reported optional capability passes",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the diagnostic command and return a process exit code."""

    args = build_parser().parse_args(argv)
    report = collect_environment_report()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(format_human_report(report))

    return 1 if args.strict and not report.strict_ready else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build no-THOR readiness evidence for privacy-safe real formal pilot v4."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "phase5_real_formal_pilot_v4.json"


def _implementation() -> object:
    path = PROJECT_ROOT / "scripts" / "run_phase5_real_formal_pilot_v2.py"
    spec = importlib.util.spec_from_file_location("phase5_real_formal_v4_shared", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load shared formal-v4 readiness executor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--readiness-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    implementation = _implementation()
    try:
        _, _, readiness = implementation.prepare_run(
            config_path=args.config.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
            execute_requested=False,
        )
    except (
        json.JSONDecodeError,
        OSError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"phase5_real_formal_v4_readiness_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(readiness, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if readiness.get("readiness_passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

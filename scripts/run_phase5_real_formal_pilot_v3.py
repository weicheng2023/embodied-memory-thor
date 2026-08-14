#!/usr/bin/env python3
"""Build readiness evidence or execute the privacy-safe real formal pilot v3."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "phase5_real_formal_pilot_v3.json"


def _implementation() -> object:
    path = PROJECT_ROOT / "scripts" / "run_phase5_real_formal_pilot_v2.py"
    spec = importlib.util.spec_from_file_location("phase5_real_formal_shared", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load shared formal executor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--readiness-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    implementation = _implementation()
    try:
        config, manifest, readiness = implementation.prepare_run(
            config_path=args.config.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
            execute_requested=args.execute,
        )
        result = (
            readiness
            if args.readiness_only
            else implementation.execute_formal(
                config=config,
                manifest=manifest,
                readiness=readiness,
                output_dir=args.output_dir.expanduser().resolve(),
            )
        )
    except (
        json.JSONDecodeError,
        OSError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"phase5_real_formal_v3_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    if args.readiness_only:
        return 0 if result.get("readiness_passed") is True else 1
    return 0 if (
        result.get("matrix_complete") is True
        and result.get("integrity_valid") is True
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())

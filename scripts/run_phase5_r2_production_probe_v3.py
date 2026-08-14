#!/usr/bin/env python3
"""Run one excluded integration triplet against frozen R2 runtime set v2."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase5.frozen_r2_v2 import (  # noqa: E402
    R2_RUNTIME_SET_VERSION_V2,
    load_frozen_r2_runtime_v2,
)


PROBE_VERSION = "phase5-r2-six-runtime-integration-probe-v3"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "phase5_r2_production_integration_probe_v3.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _legacy() -> Any:
    path = PROJECT_ROOT / "scripts" / "run_phase5_r2_production_probe.py"
    spec = importlib.util.spec_from_file_location("phase5_r2_probe_v2_frozen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen R2 probe v2 implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_probe_config(config: Mapping[str, Any], legacy: Any) -> None:
    if config.get("probe_version") != PROBE_VERSION:
        raise ValueError("probe v3 version mismatch")
    if config.get("runtime_set_version") != R2_RUNTIME_SET_VERSION_V2:
        raise ValueError("probe v3 runtime-set version mismatch")
    if config.get("configuration_id") != "FloorPlan6_R2_fixed_start_001":
        raise ValueError("probe v3 must use the pre-registered FloorPlan6 runtime")
    if config.get("episode_reuse_from_v2") is not False:
        raise ValueError("probe v3 must rerun all episodes")
    inherited = dict(config)
    inherited["probe_version"] = "phase5-r2-production-integration-probe-v2"
    inherited["episode_reuse_from_v1"] = False
    legacy.validate_probe_config(inherited)
    for relative, expected in config.get("historical_artifacts_frozen", {}).items():
        if _sha256(PROJECT_ROOT / str(relative)) != str(expected):
            raise ValueError(f"historical artifact changed: {relative}")
    serialized = json.dumps(config, sort_keys=True)
    for forbidden in ('"x"', '"y"', '"z"', "objectId", "TeleportFull", "Cup|", "CoffeeMachine|"):
        if forbidden in serialized:
            raise ValueError(f"public probe config contains private data: {forbidden}")


def _head_is_clean_and_pushed() -> bool:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    upstream = subprocess.run(
        ["git", "rev-parse", "@{upstream}"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    return not dirty and head == upstream


def run_probe(*, config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    legacy = _legacy()
    validate_probe_config(config, legacy)
    if not _head_is_clean_and_pushed():
        raise ValueError("probe v3 requires a clean pushed HEAD")
    legacy.load_frozen_r2_runtime = load_frozen_r2_runtime_v2
    legacy.validate_probe_config = lambda value: validate_probe_config(value, _legacy())
    result = legacy.run_probe(config_path=config_path, output_dir=output_dir)
    result["runtime_set_version"] = R2_RUNTIME_SET_VERSION_V2
    result["next_gate"] = (
        "pre-register the six-configuration comparison dry run"
        if result.get("passed") is True
        else "stop and diagnose the first integration failure"
    )
    legacy._write_json(output_dir / "probe_summary.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_probe(
            config_path=args.config.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
        )
    except (json.JSONDecodeError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"phase5_r2_probe_v3_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Rerun the excluded FloorPlan6 triplet with shared entry recovery v1."""

from __future__ import annotations

import argparse
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

from embodied_memory_thor.phase5.search import (  # noqa: E402
    SHARED_SEARCH_ENTRY_RECOVERY_ACTION_LIMIT,
    SHARED_SEARCH_ENTRY_RECOVERY_POLICY_VERSION,
)


PROBE_VERSION = "phase5-r2-six-runtime-integration-probe-v4"
DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "phase5_r2_production_integration_probe_v4.json"
)


def _predecessor() -> Any:
    path = PROJECT_ROOT / "scripts" / "run_phase5_r2_production_probe_v3.py"
    spec = importlib.util.spec_from_file_location("phase5_r2_probe_v3_frozen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen R2 probe v3 implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_probe_config(config: Mapping[str, Any], predecessor: Any) -> None:
    if config.get("probe_version") != PROBE_VERSION:
        raise ValueError("probe v4 version mismatch")
    if config.get("remediates_probe_version") != predecessor.PROBE_VERSION:
        raise ValueError("probe v4 predecessor mismatch")
    if config.get("episode_reuse_from_v3") is not False:
        raise ValueError("probe v4 must rerun all episodes")
    if (
        config.get("shared_search_entry_recovery_policy")
        != SHARED_SEARCH_ENTRY_RECOVERY_POLICY_VERSION
    ):
        raise ValueError("probe v4 entry-recovery policy mismatch")
    if (
        config.get("shared_search_entry_recovery_action_limit")
        != SHARED_SEARCH_ENTRY_RECOVERY_ACTION_LIMIT
    ):
        raise ValueError("probe v4 entry-recovery action limit mismatch")
    inherited = dict(config)
    inherited["probe_version"] = predecessor.PROBE_VERSION
    predecessor.validate_probe_config(inherited, predecessor._legacy())


def _enrich_and_audit(
    *,
    result: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    for row in result.get("rows", []):
        if not isinstance(row, dict):
            continue
        variant = str(row.get("variant", ""))
        summary_path = output_dir / variant / "summary.json"
        if not summary_path.is_file():
            row.setdefault("audit_errors", []).append(
                "missing_entry_recovery_summary"
            )
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        for key in (
            "shared_search_entry_recovery_policy",
            "shared_search_entry_recovery_action_limit",
            "shared_search_entry_departure_action_count",
            "shared_search_entry_recovery_action_count",
            "shared_search_entry_recovery_pending_action_count",
            "shared_search_entry_recovery_record_failure_count",
        ):
            row[key] = summary.get(key)
        errors = row.setdefault("audit_errors", [])
        if (
            row["shared_search_entry_recovery_policy"]
            != SHARED_SEARCH_ENTRY_RECOVERY_POLICY_VERSION
        ):
            errors.append("entry_recovery_policy")
        if (
            row["shared_search_entry_recovery_action_limit"]
            != SHARED_SEARCH_ENTRY_RECOVERY_ACTION_LIMIT
        ):
            errors.append("entry_recovery_action_limit")
        if row["shared_search_entry_recovery_record_failure_count"] != 0:
            errors.append("entry_recovery_record_failure")
        if summary.get("shared_search_route_entry_mismatch_count") != 0:
            errors.append("entry_recovery_route_entry_mismatch")
        if variant in {"no_memory", "short_memory_k2"} and (
            row["shared_search_entry_departure_action_count"] != 0
            or row["shared_search_entry_recovery_action_count"] != 0
        ):
            errors.append("baseline_unexpected_entry_recovery")
        if variant == "object_memory" and (
            not isinstance(row["shared_search_entry_recovery_action_count"], int)
            or row["shared_search_entry_recovery_action_count"] < 1
        ):
            errors.append("object_memory_entry_recovery_not_exercised")
        if (
            summary.get("shared_search_coverage_action_count", 0) > 0
            and row["shared_search_entry_recovery_pending_action_count"] != 0
        ):
            errors.append("coverage_started_before_entry_recovery_completed")
    result["passed"] = bool(
        len(result.get("rows", [])) == 3
        and all(not row.get("audit_errors") for row in result["rows"])
    )
    result["probe_version"] = PROBE_VERSION
    result["remediates_probe_version"] = (
        "phase5-r2-six-runtime-integration-probe-v3"
    )
    result["entry_recovery_policy"] = (
        SHARED_SEARCH_ENTRY_RECOVERY_POLICY_VERSION
    )
    result["next_gate"] = (
        "freeze the excluded v4 evidence and pre-register the six-configuration dry run"
        if result["passed"]
        else "diagnose the first remaining excluded integration failure"
    )
    return result


def run_probe(*, config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    predecessor = _predecessor()
    validate_probe_config(config, predecessor)
    original_validate = predecessor.validate_probe_config

    def validate_runtime(value: Mapping[str, Any], legacy: Any) -> None:
        predecessor.validate_probe_config = original_validate
        try:
            validate_probe_config(value, predecessor)
        finally:
            predecessor.validate_probe_config = validate_runtime

    predecessor.validate_probe_config = validate_runtime
    try:
        result = predecessor.run_probe(
            config_path=config_path,
            output_dir=output_dir,
        )
    finally:
        predecessor.validate_probe_config = original_validate
    result = _enrich_and_audit(result=result, output_dir=output_dir)
    predecessor._legacy()._write_json(output_dir / "probe_summary.json", result)
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
    except (
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        ValueError,
    ) as exc:
        print(f"phase5_r2_probe_v4_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

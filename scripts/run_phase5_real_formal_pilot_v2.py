#!/usr/bin/env python3
"""Build readiness evidence or execute the privacy-safe real 54-cell pilot."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase4.runner import (  # noqa: E402
    ThorEpisodeConfig,
    ThorEpisodeRunner,
)
from embodied_memory_thor.phase5.formal_v2 import (  # noqa: E402
    REAL_EPISODE_COUNT,
    REAL_REQUIRED_METRICS,
    build_public_manifest,
    collect_public_runtime_bindings,
    compact_result_row,
    sha256_file,
    stable_digest,
    validate_precommit,
)
from embodied_memory_thor.phase5.frozen_r1 import (  # noqa: E402
    load_frozen_r1_runtime,
)
from embodied_memory_thor.phase5.frozen_r2_v2 import (  # noqa: E402
    load_frozen_r2_runtime_v2,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "phase5_real_formal_pilot_v2.json"
EXPECTED_FORMAL_EVIDENCE_STATUS = "formal_acceptance_candidate"
FORMAL_EXECUTOR_VERSION = "phase5-real-thor-formal-executor-v2"
FORBIDDEN_ORDINARY_KEYS = {
    "anchor_id",
    "candidate_order",
    "destination_pose",
    "private_registry",
    "reachable_positions",
    "relocation_destination",
    "support_id",
    "target_point",
}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _git_state() -> tuple[str, str, bool]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    upstream = subprocess.run(
        ["git", "rev-parse", "@{upstream}"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return head, upstream, dirty


def _walk_forbidden(value: Any, path: str = "") -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            child = f"{path}.{key}" if path else key
            if key in FORBIDDEN_ORDINARY_KEYS:
                violations.append(child)
            violations.extend(_walk_forbidden(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_walk_forbidden(item, f"{path}[{index}]"))
    return violations


def _load_runtime(episode: Mapping[str, Any]) -> tuple[Any, Any, Any, Any]:
    configuration_id = str(episode["configuration_id"])
    runtime_set = str(episode["runtime_set"])
    if runtime_set == "phase5-r1-frozen-six-anchor-set-v1":
        runtime = load_frozen_r1_runtime(configuration_id)
        intervention = (
            runtime.intervention()
            if episode.get("condition") == "stale_r1"
            else None
        )
        return runtime.configuration, runtime.search_route, None, intervention
    if runtime_set == "phase5-r2-frozen-runtime-set-v2":
        runtime = load_frozen_r2_runtime_v2(configuration_id)
        return (
            runtime.configuration,
            runtime.fallback_route,
            runtime.subgoal_route,
            None,
        )
    raise ValueError(f"unsupported formal runtime set: {runtime_set}")


def build_readiness(
    *,
    config: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Join all private runtimes without exposing their content or running THOR."""

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for episode in manifest["episodes"]:
        configuration_id = str(episode["configuration_id"])
        if configuration_id in seen:
            continue
        setup, search_route, subgoal_route, _ = _load_runtime(episode)
        public = setup.public_reference()
        if str(public.get("configuration_id", "")) != configuration_id:
            raise ValueError(f"runtime configuration mismatch: {configuration_id}")
        if str(public.get("scene", "")) != str(episode["scene"]):
            raise ValueError(f"runtime scene mismatch: {configuration_id}")
        if search_route.route_id != episode["search_route_id"]:
            raise ValueError(f"runtime search route mismatch: {configuration_id}")
        if (
            search_route.action_sequence_digest
            != episode["search_route_action_sequence_digest"]
        ):
            raise ValueError(f"runtime search digest mismatch: {configuration_id}")
        if subgoal_route is None:
            if "subgoal_route_id" in episode:
                raise ValueError(f"unexpected subgoal route: {configuration_id}")
        else:
            if subgoal_route.route_id != episode.get("subgoal_route_id"):
                raise ValueError(f"runtime subgoal route mismatch: {configuration_id}")
            if subgoal_route.action_sequence_digest != episode.get(
                "subgoal_route_action_sequence_digest"
            ):
                raise ValueError(f"runtime subgoal digest mismatch: {configuration_id}")
        rows.append(
            {
                "configuration_id": configuration_id,
                "runtime_set": str(episode["runtime_set"]),
                "scene": str(episode["scene"]),
                "search_route_id": str(episode["search_route_id"]),
                "search_route_action_sequence_digest": str(
                    episode["search_route_action_sequence_digest"]
                ),
                "subgoal_route_id": episode.get("subgoal_route_id"),
                "subgoal_route_action_sequence_digest": episode.get(
                    "subgoal_route_action_sequence_digest"
                ),
                "private_runtime_joined": True,
                "private_runtime_serialized": False,
            }
        )
        seen.add(configuration_id)
    readiness = {
        "readiness_version": "phase5-real-thor-formal-readiness-v2",
        "executor_version": FORMAL_EXECUTOR_VERSION,
        "code_revision": manifest["code_revision"],
        "manifest_digest": manifest["manifest_digest"],
        "episode_count": len(manifest["episodes"]),
        "unique_runtime_count": len(rows),
        "runtime_rows": rows,
        "private_runtime_join_passed": len(rows) == 12,
        "private_runtime_material_serialized": False,
        "formal_execution_authorized": config["formal_execution_authorized"],
        "readiness_passed": len(rows) == 12,
    }
    serialized = json.dumps(readiness, ensure_ascii=False, sort_keys=True)
    if _walk_forbidden(readiness) or any(
        token in serialized
        for token in (
            "Book|",
            "CoffeeMachine|",
            "Cup|",
            "PlaceObjectAtPoint",
            "TeleportFull",
        )
    ):
        raise ValueError("readiness output contains private runtime material")
    return readiness


def audit_episode(
    *,
    episode: Mapping[str, Any],
    summary: Mapping[str, Any],
    episode_dir: Path,
    expected_code_revision: str | None = None,
) -> list[str]:
    """Separate integrity validity from the task success outcome."""

    errors: list[str] = []
    for key in REAL_REQUIRED_METRICS:
        if key not in summary:
            errors.append(f"missing_metric:{key}")
    if summary.get("information_boundary_passed") is not True:
        errors.append("information_boundary_failed")
    if summary.get("setup_completed") is not True or summary.get(
        "setup_failure_reason"
    ):
        errors.append("evaluator_setup_failed")
    if summary.get("included_in_formal_aggregate") is not True:
        errors.append("summary_formal_aggregate_label")
    if summary.get("evidence_status") != EXPECTED_FORMAL_EVIDENCE_STATUS:
        errors.append("summary_evidence_status")
    if summary.get("shared_search_action_sequence_digest") != episode.get(
        "search_route_action_sequence_digest"
    ):
        errors.append("search_route_digest")
    if summary.get("shared_search_route_id") != episode.get("search_route_id"):
        errors.append("search_route_id")
    if summary.get("shared_subgoal_action_sequence_digest") != episode.get(
        "subgoal_route_action_sequence_digest"
    ):
        errors.append("subgoal_route_digest")
    if summary.get("shared_subgoal_route_id") != episode.get("subgoal_route_id"):
        errors.append("subgoal_route_id")
    if (
        summary.get("shared_search_entry_recovery_policy")
        != "phase5-shared-search-entry-recovery-v1"
    ):
        errors.append("entry_recovery_policy")
    if summary.get("shared_search_entry_recovery_action_limit") != 64:
        errors.append("entry_recovery_action_limit")
    for key in (
        "invalid_action_count",
        "shared_search_route_entry_mismatch_count",
        "shared_search_action_failure_count",
        "shared_subgoal_route_entry_mismatch_count",
        "shared_subgoal_action_failure_count",
        "shared_search_entry_recovery_record_failure_count",
    ):
        if summary.get(key) != 0:
            errors.append(f"integrity_counter:{key}")
    if (
        summary.get("shared_search_coverage_action_count", 0) > 0
        and summary.get("shared_search_entry_recovery_pending_action_count") != 0
    ):
        errors.append("coverage_before_entry_recovery_complete")

    expected_interventions = 1 if episode.get("panel") == "r1_stale" else 0
    if summary.get("intervention_count") != expected_interventions:
        errors.append("intervention_count")
    if summary.get("intervention_failure_count") != 0:
        errors.append("intervention_failure")
    if (
        episode.get("memory") == "short_memory_k2"
        and summary.get("short_memory_evicted_before_reacquisition") is not True
    ):
        errors.append("short_memory_k2_eviction")
    progress = summary.get("task_progress", {})
    if not isinstance(progress, Mapping) or progress.get("protocol_violations"):
        errors.append("task_protocol_violation")

    manifest_path = episode_dir / "run_manifest.json"
    if not manifest_path.is_file():
        errors.append("missing_run_manifest")
    else:
        run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if run_manifest.get("included_in_formal_aggregate") is not True:
            errors.append("manifest_formal_aggregate_label")
        if run_manifest.get("evidence_status") != EXPECTED_FORMAL_EVIDENCE_STATUS:
            errors.append("manifest_evidence_status")
        if run_manifest.get("working_tree_dirty") is not False:
            errors.append("manifest_working_tree_dirty")
        if (
            expected_code_revision is not None
            and run_manifest.get("code_revision") != expected_code_revision
        ):
            errors.append("manifest_code_revision")

    ordinary_records: list[Any] = []
    for name in ("setup.jsonl", "episode.jsonl"):
        path = episode_dir / name
        if not path.is_file():
            errors.append(f"missing_ordinary_log:{name}")
            continue
        ordinary_records.extend(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    errors.extend(
        f"ordinary_forbidden_key:{path}"
        for path in _walk_forbidden(ordinary_records)
    )
    ordinary = json.dumps(ordinary_records, ensure_ascii=False, sort_keys=True)
    for native_action in ("PlaceObjectAtPoint", "TeleportFull"):
        if native_action in ordinary:
            errors.append(f"ordinary_native_action_leak:{native_action}")
    if not (episode_dir / "evaluator_setup.jsonl").is_file():
        errors.append("missing_private_setup_log")
    intervention_path = episode_dir / "intervention.jsonl"
    if expected_interventions == 1 and not intervention_path.is_file():
        errors.append("missing_private_intervention_log")
    if expected_interventions == 0 and intervention_path.exists():
        errors.append("unexpected_private_intervention_log")
    return errors


def prepare_run(
    *, config_path: Path, output_dir: Path, execute_requested: bool = False
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if output_dir.exists():
        raise ValueError("formal/readiness output directory already exists")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_precommit(config, root=PROJECT_ROOT)
    if execute_requested and config.get("formal_execution_authorized") is not True:
        raise ValueError("formal execution is not authorized by the precommit")
    head, upstream, dirty = _git_state()
    if dirty or head != upstream:
        raise ValueError("formal readiness requires a clean pushed HEAD")
    bindings = collect_public_runtime_bindings(config, root=PROJECT_ROOT)
    manifest = build_public_manifest(
        config,
        code_revision=head,
        bindings=bindings,
    )
    readiness = build_readiness(config=config, manifest=manifest)
    output_dir.mkdir(parents=True)
    _write_json(output_dir / "formal_manifest.json", manifest)
    _write_json(output_dir / "readiness.json", readiness)
    return config, manifest, readiness


def execute_formal(
    *,
    config: Mapping[str, Any],
    manifest: Mapping[str, Any],
    readiness: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    if config.get("formal_execution_authorized") is not True:
        raise ValueError("formal execution is not authorized by the precommit")
    if readiness.get("readiness_passed") is not True:
        raise ValueError("formal runtime readiness did not pass")
    rows: list[dict[str, Any]] = []
    invalidated = False
    for episode in manifest["episodes"]:
        setup, search_route, subgoal_route, intervention = _load_runtime(episode)
        episode_dir = (
            output_dir
            / "episodes"
            / f"{int(episode['episode_index']):03d}_{episode['panel']}_{episode['configuration_id']}_{episode['memory']}"
        )
        summary = ThorEpisodeRunner(
            ThorEpisodeConfig(
                task=str(episode["task"]),
                scene=str(episode["scene"]),
                planner="deterministic",
                memory=str(episode["memory"]),
                search_route_id=search_route.route_id,
                subgoal_route_id=(
                    subgoal_route.route_id if subgoal_route is not None else None
                ),
                condition=str(episode["condition"]),
                mode="formal",
                max_steps=int(episode["max_steps"]),
                output_dir=episode_dir,
                save_frames=False,
                trace_html=False,
                visualize=False,
                save_evaluator_debug=False,
                included_in_formal_aggregate=True,
                run_purpose=str(config["run_purpose"]),
                controller_settings=dict(config["controller_settings"]),
            ),
            search_route=search_route,
            subgoal_route=subgoal_route,
            evaluator_setup=setup,
            intervention=intervention,
        ).run()
        integrity_errors = audit_episode(
            episode=episode,
            summary=summary,
            episode_dir=episode_dir,
            expected_code_revision=str(manifest["code_revision"]),
        )
        rows.append(
            compact_result_row(
                episode=episode,
                summary=summary,
                integrity_errors=integrity_errors,
            )
        )
        _write_json(
            output_dir / "formal_progress.json",
            {
                "executor_version": FORMAL_EXECUTOR_VERSION,
                "code_revision": manifest["code_revision"],
                "manifest_digest": manifest["manifest_digest"],
                "completed_episode_count": len(rows),
                "integrity_valid_so_far": not any(
                    row["integrity_errors"] for row in rows
                ),
                "rows": rows,
            },
        )
        if integrity_errors:
            invalidated = True
            break
    result = {
        "executor_version": FORMAL_EXECUTOR_VERSION,
        "code_revision": manifest["code_revision"],
        "manifest_digest": manifest["manifest_digest"],
        "completed_episode_count": len(rows),
        "expected_episode_count": REAL_EPISODE_COUNT,
        "matrix_complete": len(rows) == REAL_EPISODE_COUNT,
        "integrity_valid": not invalidated and not any(
            row["integrity_errors"] for row in rows
        ),
        "included_in_formal_aggregate": bool(
            len(rows) == REAL_EPISODE_COUNT and not invalidated
        ),
        "task_success_count": sum(row.get("success") is True for row in rows),
        "task_failure_count": sum(row.get("success") is False for row in rows),
        "rows": rows,
        "result_digest": stable_digest(rows),
        "next_gate": (
            "aggregate and report the complete fixed matrix"
            if len(rows) == REAL_EPISODE_COUNT and not invalidated
            else "retain the invalidated partial matrix; diagnose and version a complete rerun"
        ),
    }
    _write_json(output_dir / "formal_summary.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--readiness-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        config, manifest, readiness = prepare_run(
            config_path=args.config.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
            execute_requested=args.execute,
        )
        if args.readiness_only:
            result = readiness
        else:
            result = execute_formal(
                config=config,
                manifest=manifest,
                readiness=readiness,
                output_dir=args.output_dir.expanduser().resolve(),
            )
    except (
        json.JSONDecodeError,
        OSError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"phase5_real_formal_v2_error: {exc}", file=sys.stderr)
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

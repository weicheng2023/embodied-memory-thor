#!/usr/bin/env python3
"""Run the complete frozen 30-cell Phase-7B memory-horizon matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase4.runner import ThorEpisodeRunner  # noqa: E402
from embodied_memory_thor.phase4.task import (  # noqa: E402
    PHASE5_BOOK_DISTRACTION_POLICY_V4,
)
from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.phase7.holdout import (  # noqa: E402
    load_phase7a_holdout_runtime,
    validate_public_artifact,
)
from embodied_memory_thor.phase7.recent_memory import (  # noqa: E402
    PHASE7B_RECENT_CAPACITIES,
    PHASE7B_RECENT_MEMORY_VERSION,
    PHASE7B_VARIANTS,
    Phase7BThorEpisodeConfig,
    build_phase7b_memory,
    recent_capacity,
)


DEFAULT_MANIFEST = (
    PROJECT_ROOT / "configs" / "phase7" / "memory_horizon_manifest.json"
)
DEFAULT_REQUIRED_TAG = "phase7b-memory-horizon-matrix-v1"
REQUIRED_SUMMARY_METRICS = (
    "success",
    "steps",
    "target_reacquisition_action_count",
    "translation_action_count",
    "translation_distance_meters",
    "search_rotation_count",
    "repeated_viewpoint_visit_count",
    "memory_guided_action_count",
    "memory_retrieval_count",
    "invalid_action_count",
    "invalid_planner_decision_count",
    "failed_interaction_count",
    "shared_search_entry_recovery_action_count",
    "shared_search_coverage_action_count",
    "shared_route_action_recovery_attempt_count",
    "shared_route_action_recovery_action_count",
    "shared_route_action_recovered_failure_count",
    "shared_route_action_recovery_terminal_failure_count",
    "target_lock_interaction_recovery_action_count",
    "target_lock_interaction_recovery_attempt_count",
    "target_lock_terminal_failure_count",
    "information_boundary_passed",
)
_RETENTION_STAGES = frozenset({"reacquire_book", "pickup_book"})


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return "<external-output>"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _assert_clean_pushed_tag(required_tag: str) -> str:
    revision = _git("rev-parse", "HEAD")
    if _git("status", "--porcelain"):
        raise ValueError("Phase7B matrix requires a clean worktree")
    if _git("rev-parse", "@{upstream}") != revision:
        raise ValueError("Phase7B matrix requires HEAD to match upstream")
    if _git("rev-list", "-n", "1", required_tag) != revision:
        raise ValueError(f"Phase7B matrix requires HEAD at tag {required_tag}")
    return revision


def validate_memory_horizon_manifest(manifest: Mapping[str, Any]) -> None:
    errors: list[str] = []
    if manifest.get("status") != "matrix_frozen_no_outcomes":
        errors.append("status")
    if manifest.get("outcome_execution_authorized") is not True:
        errors.append("outcome_execution_authorized")
    if tuple(manifest.get("variants", ())) != PHASE7B_VARIANTS:
        errors.append("variants")
    if manifest.get("recent_capacity_by_variant") != PHASE7B_RECENT_CAPACITIES:
        errors.append("recent_capacity_by_variant")
    if manifest.get("recent_memory_provider") != PHASE7B_RECENT_MEMORY_VERSION:
        errors.append("recent_memory_provider")
    configuration_ids = manifest.get("configuration_ids", [])
    if not isinstance(configuration_ids, list) or len(configuration_ids) != 6:
        errors.append("configuration_ids")
    elif len(set(configuration_ids)) != len(configuration_ids):
        errors.append("duplicate_configuration_id")
    if int(manifest.get("expected_episode_count", 0)) != 30:
        errors.append("expected_episode_count")
    if manifest.get("success_budgets") != [18, 72, 2048]:
        errors.append("success_budgets")
    if int(manifest.get("max_steps_per_episode", 0)) != 2048:
        errors.append("max_steps_per_episode")
    if manifest.get("prior_episode_reuse") is not False:
        errors.append("prior_episode_reuse")
    if manifest.get("optional_persistent_snapshot_memory_used") is not False:
        errors.append("optional_persistent_snapshot_memory_used")
    digest_payload = deepcopy(dict(manifest))
    expected_digest = str(digest_payload.pop("manifest_digest", ""))
    if stable_digest(digest_payload) != expected_digest:
        errors.append("manifest_digest")
    try:
        validate_public_artifact(manifest)
    except Exception:
        errors.append("public_information_boundary")
    if errors:
        raise ValueError("invalid Phase7B matrix manifest: " + ",".join(errors))


def validate_bound_sources(manifest: Mapping[str, Any]) -> None:
    source_manifest_path = PROJECT_ROOT / str(manifest["configuration_source"])
    private_path = PROJECT_ROOT / str(manifest["evaluator_registry"])
    route_path = PROJECT_ROOT / str(manifest["route_registry"])
    errors: list[str] = []
    for path, key in (
        (source_manifest_path, "configuration_source_sha256"),
        (private_path, "evaluator_registry_sha256"),
        (route_path, "route_registry_sha256"),
    ):
        if not path.is_file() or _sha256(path) != str(manifest.get(key, "")):
            errors.append(key)
    if source_manifest_path.is_file():
        source = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        source_ids = [
            str(row.get("configuration_id", ""))
            for row in source.get("selected_configurations", [])
            if isinstance(row, Mapping)
        ]
        if source_ids != list(manifest.get("configuration_ids", [])):
            errors.append("configuration_source_order")
    source_tag = str(manifest.get("source_phase7a_result_tag", ""))
    source_revision = str(manifest.get("source_phase7a_result_revision", ""))
    try:
        if _git("rev-list", "-n", "1", source_tag) != source_revision:
            errors.append("source_phase7a_result_tag")
    except subprocess.CalledProcessError:
        errors.append("source_phase7a_result_tag")
    if errors:
        raise ValueError("invalid Phase7B bound source: " + ",".join(errors))


def retention_checkpoint(
    trace_path: Path, *, target_object_id: str
) -> dict[str, Any]:
    """Reduce the first reacquisition request to non-identifying scalars."""

    with trace_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            request = (
                row.get("planner_input", {}).get("request", {})
                if isinstance(row, Mapping)
                else {}
            )
            if request.get("task_stage") not in _RETENTION_STAGES:
                continue
            retrieved = request.get("retrieved_memory", [])
            if not isinstance(retrieved, list):
                retrieved = []
            target_records = [
                record
                for record in retrieved
                if isinstance(record, Mapping)
                and str(record.get("object_id", "")) == target_object_id
            ]
            last_seen_steps = [
                int(record["last_seen_step"])
                for record in target_records
                if isinstance(record.get("last_seen_step"), int)
            ]
            checkpoint_step = int(request.get("step", row.get("step", 0)))
            last_seen_step = max(last_seen_steps) if last_seen_steps else None
            memory_before = row.get("environment_feedback", {}).get(
                "memory_before", {}
            )
            if not isinstance(memory_before, Mapping):
                memory_before = {}
            observation_ids = memory_before.get("observation_ids", [])
            return {
                "retention_checkpoint_found": True,
                "retention_checkpoint_step": checkpoint_step,
                "retention_checkpoint_stage": str(request["task_stage"]),
                "target_record_present_at_reacquisition": bool(target_records),
                "target_record_count_at_reacquisition": len(target_records),
                "target_record_last_seen_step_at_reacquisition": last_seen_step,
                "target_record_age_actions_at_reacquisition": (
                    checkpoint_step - last_seen_step
                    if last_seen_step is not None
                    else None
                ),
                "memory_provider_kind_at_reacquisition": memory_before.get("kind"),
                "recent_capacity_at_reacquisition": memory_before.get("k"),
                "recent_observation_count_at_reacquisition": (
                    len(observation_ids) if isinstance(observation_ids, list) else None
                ),
            }
    return {
        "retention_checkpoint_found": False,
        "retention_checkpoint_step": None,
        "retention_checkpoint_stage": None,
        "target_record_present_at_reacquisition": None,
        "target_record_count_at_reacquisition": None,
        "target_record_last_seen_step_at_reacquisition": None,
        "target_record_age_actions_at_reacquisition": None,
        "memory_provider_kind_at_reacquisition": None,
        "recent_capacity_at_reacquisition": None,
        "recent_observation_count_at_reacquisition": None,
    }


def _episode_integrity_errors(
    *,
    summary: Mapping[str, Any],
    run_manifest: Mapping[str, Any],
    retention: Mapping[str, Any],
    expected_revision: str,
    expected_variant: str,
    expected_route_digest: str,
) -> list[str]:
    errors: list[str] = []
    for metric in REQUIRED_SUMMARY_METRICS:
        if metric not in summary:
            errors.append(f"missing_metric:{metric}")
    if run_manifest.get("code_revision") != expected_revision:
        errors.append("code_revision_mismatch")
    if run_manifest.get("working_tree_dirty") is not False:
        errors.append("working_tree_dirty")
    if summary.get("memory") != expected_variant:
        errors.append("memory_variant_mismatch")
    if summary.get("book_distraction_policy") != PHASE5_BOOK_DISTRACTION_POLICY_V4:
        errors.append("book_distraction_policy_mismatch")
    if summary.get("shared_search_action_sequence_digest") != expected_route_digest:
        errors.append("route_digest_mismatch")
    if summary.get("information_boundary_passed") is not True:
        errors.append("information_boundary_failed")
    if int(summary.get("invalid_planner_decision_count", -1)) != 0:
        errors.append("invalid_planner_decision")
    if summary.get("rgb_consumed_by_planner") is not False:
        errors.append("rgb_consumed_by_planner")
    if summary.get("evaluator_debug_saved") is not False:
        errors.append("evaluator_debug_saved")
    if summary.get("run_purpose") != "phase7b_memory_horizon_v1":
        errors.append("run_purpose_mismatch")
    if summary.get("evidence_status") != "formal_acceptance_candidate":
        errors.append("evidence_status_mismatch")
    if summary.get("setup_completed") is not True:
        errors.append("frozen_setup_failed")
    if retention.get("retention_checkpoint_found") is not True:
        errors.append("retention_checkpoint_missing")

    expected_capacity = recent_capacity(expected_variant)
    actual_capacity = retention.get("recent_capacity_at_reacquisition")
    if expected_capacity is not None and actual_capacity != expected_capacity:
        errors.append("recent_capacity_mismatch")
    if expected_capacity is None and actual_capacity is not None:
        errors.append("unexpected_recent_capacity")
    expected_kind = (
        "short"
        if expected_capacity is not None
        else ("none" if expected_variant == "no_memory" else "object")
    )
    if retention.get("memory_provider_kind_at_reacquisition") != expected_kind:
        errors.append("memory_provider_kind_mismatch")
    if (
        expected_variant == "no_memory"
        and retention.get("target_record_present_at_reacquisition") is not False
    ):
        errors.append("no_memory_retained_target")
    if int(retention.get("target_record_count_at_reacquisition") or 0) > 1:
        errors.append("duplicate_target_record")
    return errors


def compact_result_row(
    *,
    episode_index: int,
    configuration_id: str,
    summary: Mapping[str, Any],
    retention: Mapping[str, Any],
    integrity_errors: Sequence[str],
    budgets: Sequence[int],
) -> dict[str, Any]:
    success = summary.get("success") is True
    steps = summary.get("steps")
    row = {
        "episode_index": episode_index,
        "configuration_id": configuration_id,
        "scene": summary.get("scene"),
        "memory": summary.get("memory"),
        "recent_capacity": recent_capacity(str(summary.get("memory", ""))),
        "success": summary.get("success"),
        "failure_reason": summary.get("failure_reason"),
        "steps": steps,
        "target_reacquisition_action_count": summary.get(
            "target_reacquisition_action_count"
        ),
        "translation_action_count": summary.get("translation_action_count"),
        "translation_distance_meters": summary.get(
            "translation_distance_meters"
        ),
        "search_rotation_count": summary.get("search_rotation_count"),
        "repeated_viewpoint_visit_count": summary.get(
            "repeated_viewpoint_visit_count"
        ),
        "memory_guided_action_count": summary.get("memory_guided_action_count"),
        "memory_retrieval_count": summary.get("memory_retrieval_count"),
        "invalid_action_count": summary.get("invalid_action_count"),
        "invalid_planner_decision_count": summary.get(
            "invalid_planner_decision_count"
        ),
        "failed_interaction_count": summary.get("failed_interaction_count"),
        "shared_search_entry_recovery_action_count": summary.get(
            "shared_search_entry_recovery_action_count"
        ),
        "shared_search_coverage_action_count": summary.get(
            "shared_search_coverage_action_count"
        ),
        "shared_route_action_recovery_attempt_count": summary.get(
            "shared_route_action_recovery_attempt_count"
        ),
        "shared_route_action_recovery_action_count": summary.get(
            "shared_route_action_recovery_action_count"
        ),
        "shared_route_action_recovered_failure_count": summary.get(
            "shared_route_action_recovered_failure_count"
        ),
        "shared_route_action_recovery_terminal_failure_count": summary.get(
            "shared_route_action_recovery_terminal_failure_count"
        ),
        "target_lock_interaction_recovery_action_count": summary.get(
            "target_lock_interaction_recovery_action_count"
        ),
        "target_lock_interaction_recovery_attempt_count": summary.get(
            "target_lock_interaction_recovery_attempt_count"
        ),
        "target_lock_terminal_failure_count": summary.get(
            "target_lock_terminal_failure_count"
        ),
        "information_boundary_passed": summary.get("information_boundary_passed"),
        **dict(retention),
        "integrity_errors": list(integrity_errors),
    }
    if not isinstance(steps, int):
        success = False
    for budget in budgets:
        row[f"success_at_{budget}"] = bool(success and int(steps) <= int(budget))
    validate_public_artifact(row)
    return row


def run_matrix(
    *, manifest_path: Path, output_dir: Path, required_tag: str
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_memory_horizon_manifest(manifest)
    validate_bound_sources(manifest)
    revision = _assert_clean_pushed_tag(required_tag)
    if output_dir.exists():
        raise ValueError("Phase7B matrix output directory already exists")
    output_dir.mkdir(parents=True)
    launch = {
        "execution_version": "phase7b-memory-horizon-execution-v1",
        "code_revision": revision,
        "required_tag": required_tag,
        "matrix_manifest": str(manifest_path.relative_to(PROJECT_ROOT)),
        "matrix_manifest_sha256": _sha256(manifest_path),
        "matrix_manifest_digest": manifest["manifest_digest"],
        "command_used": (
            "python scripts/phase7/run_memory_horizon.py "
            "--manifest configs/phase7/memory_horizon_manifest.json "
            f"--output-dir {_display_path(output_dir)} --required-tag {required_tag}"
        ),
        "expected_episode_count": int(manifest["expected_episode_count"]),
        "prior_episode_reuse": False,
        "images_saved": False,
        "gui_used": False,
    }
    _write_json(output_dir / "launch_manifest.json", launch)

    rows: list[dict[str, Any]] = []
    integrity_valid = True
    budgets = [int(value) for value in manifest["success_budgets"]]
    for configuration_id in manifest["configuration_ids"]:
        runtime = load_phase7a_holdout_runtime(str(configuration_id))
        for variant in PHASE7B_VARIANTS:
            episode_index = len(rows) + 1
            episode_dir = output_dir / f"{episode_index:03d}_{configuration_id}_{variant}"
            summary = ThorEpisodeRunner(
                Phase7BThorEpisodeConfig(
                    task="thor_book_reacquire_k2",
                    scene=runtime.configuration.scene,
                    planner="deterministic",
                    memory=variant,
                    book_distraction_policy=PHASE5_BOOK_DISTRACTION_POLICY_V4,
                    search_route_id=runtime.search_route.route_id,
                    condition="stable",
                    mode="formal",
                    max_steps=int(manifest["max_steps_per_episode"]),
                    output_dir=episode_dir,
                    save_frames=False,
                    trace_html=False,
                    visualize=False,
                    save_evaluator_debug=False,
                    included_in_formal_aggregate=True,
                    run_purpose="phase7b_memory_horizon_v1",
                    controller_settings=deepcopy(dict(manifest["controller_settings"])),
                ),
                memory=build_phase7b_memory(variant),
                search_route=runtime.search_route,
                evaluator_setup=runtime.configuration,
            ).run()
            run_manifest = json.loads(
                (episode_dir / "run_manifest.json").read_text(encoding="utf-8")
            )
            retention = retention_checkpoint(
                episode_dir / "episode.jsonl",
                target_object_id=runtime.configuration.target_object_id,
            )
            errors = _episode_integrity_errors(
                summary=summary,
                run_manifest=run_manifest,
                retention=retention,
                expected_revision=revision,
                expected_variant=variant,
                expected_route_digest=runtime.search_route.action_sequence_digest,
            )
            row = compact_result_row(
                episode_index=episode_index,
                configuration_id=str(configuration_id),
                summary=summary,
                retention=retention,
                integrity_errors=errors,
                budgets=budgets,
            )
            rows.append(row)
            _write_json(
                output_dir / "matrix_progress.json",
                {
                    **launch,
                    "completed_episode_count": len(rows),
                    "rows": rows,
                    "integrity_valid_so_far": all(
                        not item["integrity_errors"] for item in rows
                    ),
                },
            )
            print(
                json.dumps(
                    {
                        "episode_index": episode_index,
                        "configuration_id": configuration_id,
                        "memory": variant,
                        "recent_capacity": recent_capacity(variant),
                        "target_record_present_at_reacquisition": retention.get(
                            "target_record_present_at_reacquisition"
                        ),
                        "success": row["success"],
                        "steps": row["steps"],
                        "integrity_errors": errors,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if errors:
                integrity_valid = False
                break
        if not integrity_valid:
            break

    expected_count = launch["expected_episode_count"]
    result = {
        "evidence_version": "phase7b-memory-horizon-complete-v1",
        **launch,
        "completed_episode_count": len(rows),
        "matrix_complete": len(rows) == expected_count,
        "integrity_valid": integrity_valid and len(rows) == expected_count,
        "task_success_count": sum(row["success"] is True for row in rows),
        "task_failure_count": sum(row["success"] is not True for row in rows),
        "rows": rows,
        "claim_boundary": "fresh paired Phase7B mechanism evidence; recent-memory capacity is isolated within one provider family, but object-memory representation and retrieval remain different",
    }
    validate_public_artifact(result)
    result["result_digest"] = stable_digest(result)
    _write_json(output_dir / "memory_horizon_summary.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--required-tag", default=DEFAULT_REQUIRED_TAG)
    args = parser.parse_args(argv)
    result = run_matrix(
        manifest_path=args.manifest.resolve(),
        output_dir=args.output_dir.resolve(),
        required_tag=str(args.required_tag),
    )
    print(
        "SUMMARY "
        + json.dumps(
            {
                "matrix_complete": result["matrix_complete"],
                "integrity_valid": result["integrity_valid"],
                "task_success_count": result["task_success_count"],
                "task_failure_count": result["task_failure_count"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if result["matrix_complete"] and result["integrity_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

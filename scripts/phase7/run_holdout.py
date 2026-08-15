#!/usr/bin/env python3
"""Run one complete matrix-frozen Phase-7A holdout comparison."""

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

from embodied_memory_thor.phase4.runner import (  # noqa: E402
    ThorEpisodeConfig,
    ThorEpisodeRunner,
)
from embodied_memory_thor.phase4.task import (  # noqa: E402
    PHASE5_BOOK_DISTRACTION_POLICY_V4,
)
from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.phase7.holdout import (  # noqa: E402
    PHASE7A_VARIANTS,
    load_phase7a_holdout_runtime,
    validate_public_artifact,
)


DEFAULT_MANIFEST = PROJECT_ROOT / "configs" / "phase7" / "holdout_manifest.json"
DEFAULT_REQUIRED_TAG = "phase7a-holdout-matrix-v1"
REQUIRED_METRICS = (
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
    "short_memory_evicted_before_reacquisition",
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
        ["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _assert_clean_pushed_tag(required_tag: str) -> str:
    revision = _git("rev-parse", "HEAD")
    if _git("status", "--porcelain"):
        raise ValueError("Phase7A matrix requires a clean worktree")
    if _git("rev-parse", "@{upstream}") != revision:
        raise ValueError("Phase7A matrix requires HEAD to match upstream")
    if _git("rev-list", "-n", "1", required_tag) != revision:
        raise ValueError(f"Phase7A matrix requires HEAD at tag {required_tag}")
    return revision


def validate_matrix_manifest(manifest: Mapping[str, Any]) -> None:
    errors: list[str] = []
    if manifest.get("status") != "matrix_frozen_no_outcomes":
        errors.append("status")
    if manifest.get("outcome_execution_authorized") is not True:
        errors.append("outcome_execution_authorized")
    if tuple(manifest.get("variants", ())) != PHASE7A_VARIANTS:
        errors.append("variants")
    rows = manifest.get("selected_configurations", [])
    target_count = int(manifest.get("target_configuration_count", 0))
    if not isinstance(rows, list) or len(rows) != target_count:
        errors.append("selected_configurations")
    elif len({row.get("configuration_id") for row in rows}) != len(rows):
        errors.append("duplicate_configuration_id")
    if manifest.get("success_budgets") != [18, 72, 2048]:
        errors.append("success_budgets")
    if int(manifest.get("max_steps_per_episode", 0)) != 2048:
        errors.append("max_steps_per_episode")
    digest_payload = deepcopy(dict(manifest))
    expected_digest = str(digest_payload.pop("manifest_digest", ""))
    if stable_digest(digest_payload) != expected_digest:
        errors.append("manifest_digest")
    try:
        validate_public_artifact(manifest)
    except Exception:
        errors.append("public_information_boundary")
    if errors:
        raise ValueError("invalid Phase7A matrix manifest: " + ",".join(errors))


def _episode_integrity_errors(
    *,
    summary: Mapping[str, Any],
    run_manifest: Mapping[str, Any],
    expected_revision: str,
    expected_variant: str,
    expected_route_digest: str,
) -> list[str]:
    errors: list[str] = []
    for metric in REQUIRED_METRICS:
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
    if summary.get("run_purpose") != "phase7a_untouched_holdout_v1":
        errors.append("run_purpose_mismatch")
    if summary.get("evidence_status") != "formal_acceptance_candidate":
        errors.append("evidence_status_mismatch")
    if summary.get("setup_completed") is not True:
        errors.append("frozen_setup_failed")
    if (
        expected_variant == "short_memory_k2"
        and summary.get("success") is True
        and summary.get("short_memory_evicted_before_reacquisition") is not True
    ):
        errors.append("successful_k2_episode_without_eviction")
    return errors


def compact_result_row(
    *,
    episode_index: int,
    configuration_id: str,
    summary: Mapping[str, Any],
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
        "short_memory_evicted_before_reacquisition": summary.get(
            "short_memory_evicted_before_reacquisition"
        ),
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
        "integrity_errors": list(integrity_errors),
    }
    if not isinstance(steps, int):
        success = False
    for budget in budgets:
        row[f"success_at_{budget}"] = bool(success and int(steps) <= int(budget))
    return row


def run_matrix(
    *, manifest_path: Path, output_dir: Path, required_tag: str
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_matrix_manifest(manifest)
    revision = _assert_clean_pushed_tag(required_tag)
    if output_dir.exists():
        raise ValueError("Phase7A matrix output directory already exists")
    output_dir.mkdir(parents=True)
    launch = {
        "execution_version": "phase7a-untouched-holdout-execution-v1",
        "code_revision": revision,
        "required_tag": required_tag,
        "matrix_manifest": str(manifest_path.relative_to(PROJECT_ROOT)),
        "matrix_manifest_sha256": _sha256(manifest_path),
        "matrix_manifest_digest": manifest["manifest_digest"],
        "command_used": (
            "python scripts/phase7/run_holdout.py "
            "--manifest configs/phase7/holdout_manifest.json "
            f"--output-dir {_display_path(output_dir)} --required-tag {required_tag}"
        ),
        "expected_episode_count": int(manifest["target_configuration_count"])
        * len(PHASE7A_VARIANTS),
        "prior_episode_reuse": False,
        "images_saved": False,
        "gui_used": False,
    }
    _write_json(output_dir / "launch_manifest.json", launch)

    rows: list[dict[str, Any]] = []
    integrity_valid = True
    budgets = [int(value) for value in manifest["success_budgets"]]
    private_path = PROJECT_ROOT / str(manifest["evaluator_registry"])
    route_path = PROJECT_ROOT / str(manifest["route_registry"])
    for selected in manifest["selected_configurations"]:
        configuration_id = str(selected["configuration_id"])
        runtime = load_phase7a_holdout_runtime(
            configuration_id,
            manifest_path=manifest_path,
            private_registry_path=private_path,
            route_registry_path=route_path,
        )
        for variant in PHASE7A_VARIANTS:
            episode_index = len(rows) + 1
            episode_dir = output_dir / f"{episode_index:03d}_{configuration_id}_{variant}"
            summary = ThorEpisodeRunner(
                ThorEpisodeConfig(
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
                    run_purpose="phase7a_untouched_holdout_v1",
                    controller_settings=deepcopy(dict(manifest["controller_settings"])),
                ),
                search_route=runtime.search_route,
                evaluator_setup=runtime.configuration,
            ).run()
            run_manifest = json.loads(
                (episode_dir / "run_manifest.json").read_text(encoding="utf-8")
            )
            errors = _episode_integrity_errors(
                summary=summary,
                run_manifest=run_manifest,
                expected_revision=revision,
                expected_variant=variant,
                expected_route_digest=runtime.search_route.action_sequence_digest,
            )
            row = compact_result_row(
                episode_index=episode_index,
                configuration_id=configuration_id,
                summary=summary,
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
        "evidence_version": "phase7a-untouched-holdout-complete-v1",
        **launch,
        "completed_episode_count": len(rows),
        "matrix_complete": len(rows) == expected_count,
        "integrity_valid": integrity_valid and len(rows) == expected_count,
        "task_success_count": sum(row["success"] is True for row in rows),
        "task_failure_count": sum(row["success"] is not True for row in rows),
        "rows": rows,
        "claim_boundary": "fresh Phase7A holdout outcomes under one frozen generic policy; descriptive paired evidence only and no Phase5 result replacement",
    }
    result["result_digest"] = stable_digest(result)
    _write_json(output_dir / "holdout_summary.json", result)
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

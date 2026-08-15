#!/usr/bin/env python3
"""Select Phase-7A holdouts with fixed pre-outcome eligibility gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.phase5.search import SEARCH_ROUTE_SCHEMA_VERSION  # noqa: E402
from embodied_memory_thor.phase7.holdout import (  # noqa: E402
    PHASE7A_GENERIC_ROUTE_POLICY_VERSION,
    PHASE7A_PRIVATE_BOUNDARY,
    PHASE7A_PRIVATE_REGISTRY_VERSION,
    PHASE7A_ROUTE_REGISTRY_VERSION,
    build_phase7a_generic_route,
    build_public_route_contract,
    distraction_actions_for_horizon,
    normalize_interactable_pose,
    pose_sort_key,
    validate_public_artifact,
)


DEFAULT_MANIFEST = PROJECT_ROOT / "configs" / "phase7" / "holdout_manifest.json"
DEFAULT_POOL = PROJECT_ROOT / "configs" / "phase7" / "holdout_candidate_pool.json"
DEFAULT_REQUIRED_TAG = "phase7a-holdout-protocol-v1"


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
        raise ValueError("Phase7A eligibility requires a clean worktree")
    if _git("rev-parse", "@{upstream}") != revision:
        raise ValueError("Phase7A eligibility requires HEAD to match upstream")
    if _git("rev-list", "-n", "1", required_tag) != revision:
        raise ValueError(
            f"Phase7A eligibility requires HEAD at annotated tag {required_tag}"
        )
    return revision


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _objects(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = metadata.get("objects", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _first_book(metadata: Mapping[str, Any]) -> Mapping[str, Any] | None:
    books = sorted(
        (
            item
            for item in _objects(metadata)
            if item.get("objectType") == "Book" and item.get("pickupable") is True
        ),
        key=lambda item: str(item.get("objectId", "")),
    )
    return books[0] if books else None


def _target_visible(metadata: Mapping[str, Any], object_id: str) -> bool:
    return any(
        item.get("objectId") == object_id and item.get("visible") is True
        for item in _objects(metadata)
    )


def _reset_book(controller: Any, scene: str) -> tuple[Mapping[str, Any], str]:
    event = controller.reset(scene=scene)
    target = _first_book(event.metadata)
    if target is None or not target.get("objectId"):
        raise RuntimeError("pickupable Book unavailable after reset")
    return event.metadata, str(target["objectId"])


def _teleport(controller: Any, pose: Mapping[str, Any]) -> Any:
    return controller.step(action="TeleportFull", **dict(pose))


def _native_pickup_trial(controller: Any, scene: str, pose: Mapping[str, Any]) -> str:
    _, object_id = _reset_book(controller, scene)
    teleport = _teleport(controller, pose)
    if teleport.metadata.get("lastActionSuccess") is not True:
        raise RuntimeError("teleport_failed")
    if not _target_visible(teleport.metadata, object_id):
        raise RuntimeError("book_not_visible_after_teleport")
    pickup = controller.step(action="PickupObject", objectId=object_id)
    if pickup.metadata.get("lastActionSuccess") is not True:
        raise RuntimeError("native_pickup_failed")
    return object_id


def _distraction_hidden_trial(
    controller: Any, scene: str, pose: Mapping[str, Any]
) -> str:
    _, object_id = _reset_book(controller, scene)
    teleport = _teleport(controller, pose)
    if teleport.metadata.get("lastActionSuccess") is not True:
        raise RuntimeError("distraction_teleport_failed")
    if not _target_visible(teleport.metadata, object_id):
        raise RuntimeError("distraction_initial_book_not_visible")
    event = teleport
    for action_name in distraction_actions_for_horizon(float(pose["horizon"])):
        event = controller.step(action=action_name)
        if event.metadata.get("lastActionSuccess") is not True:
            raise RuntimeError(f"distraction_action_failed:{action_name}")
    if _target_visible(event.metadata, object_id):
        raise RuntimeError("book_visible_after_distraction_v4")
    return object_id


def _construct_route(
    controller: Any,
    scene: str,
    pose: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    _reset_book(controller, scene)
    teleport = _teleport(controller, pose)
    if teleport.metadata.get("lastActionSuccess") is not True:
        raise RuntimeError("route_teleport_failed")
    reachable_event = controller.step(action="GetReachablePositions")
    reachable = reachable_event.metadata.get("actionReturn")
    if (
        reachable_event.metadata.get("lastActionSuccess") is not True
        or not isinstance(reachable, list)
        or not reachable
    ):
        raise RuntimeError("reachable_positions_query_failed")
    return build_phase7a_generic_route(
        reachable_positions=reachable,
        start_pose=pose,
        grid_size=float(manifest["controller_settings"]["gridSize"]),
        bin_size_steps=int(manifest["route_grid_bin_size_steps"]),
        action_limit=int(manifest["route_action_limit"]),
    )


def _qualify_scene(
    controller: Any,
    scene: str,
    *,
    manifest: Mapping[str, Any],
    max_pose_trials: int,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    public_row: dict[str, Any] = {
        "scene": scene,
        "eligible": False,
        "classification": "not_evaluated",
    }
    reset_metadata, object_id = _reset_book(controller, scene)
    pose_event = controller.step(action="GetInteractablePoses", objectId=object_id)
    if pose_event.metadata.get("lastActionSuccess") is not True:
        public_row["classification"] = "interactable_pose_query_failed"
        return public_row, None, None
    raw_poses = pose_event.metadata.get("actionReturn") or []
    poses = sorted(
        (
            pose
            for pose in (
                normalize_interactable_pose(raw)
                for raw in raw_poses
                if isinstance(raw, Mapping)
            )
            if pose is not None
        ),
        key=pose_sort_key,
    )
    public_row["normalized_pose_count"] = len(poses)
    if not poses:
        public_row["classification"] = "no_normalized_interactable_pose"
        return public_row, None, None

    failure_counts: Counter[str] = Counter()
    for pose_index, pose in enumerate(poses[:max_pose_trials], start=1):
        try:
            _native_pickup_trial(controller, scene, pose)
            _distraction_hidden_trial(controller, scene, pose)
            route = _construct_route(controller, scene, pose, manifest=manifest)
        except Exception as exc:
            failure_counts[str(exc)] += 1
            continue
        _, selected_object_id = _reset_book(controller, scene)
        final_teleport = _teleport(controller, pose)
        if (
            final_teleport.metadata.get("lastActionSuccess") is not True
            or not _target_visible(final_teleport.metadata, selected_object_id)
        ):
            failure_counts["final_freeze_replay_failed"] += 1
            continue
        configuration_id = f"{scene}_Phase7A_R1_holdout_001"
        route_contract = build_public_route_contract(
            scene=scene,
            configuration_id=configuration_id,
            route=route,
        )
        start_pose_digest = stable_digest(pose)
        public_row.update(
            {
                "configuration_id": configuration_id,
                "eligible": True,
                "classification": "eligible",
                "selected_pose_order": pose_index,
                "start_pose_digest": start_pose_digest,
                "route_id": route_contract["route_id"],
                "route_action_sequence_digest": route_contract[
                    "action_sequence_digest"
                ],
                "route_construction_digest": route["route_digest"],
                "route_action_count": route["action_count"],
                "route_viewpoint_count": route["viewpoint_count"],
                "route_reachable_node_count": route["reachable_node_count"],
                "route_coverage_summary": route["coverage_summary"],
            }
        )
        private_row = {
            "configuration_id": configuration_id,
            "scene": scene,
            "target_object_id": selected_object_id,
            "start_action": {"action": "TeleportFull", **deepcopy(pose)},
            "start_pose_digest": start_pose_digest,
            "route_id": route_contract["route_id"],
        }
        validate_public_artifact(public_row)
        return public_row, private_row, route_contract

    public_row.update(
        {
            "classification": "no_pose_passed_fixed_eligibility_gates",
            "pose_trials_attempted": min(len(poses), max_pose_trials),
            "failure_category_counts": dict(sorted(failure_counts.items())),
        }
    )
    validate_public_artifact(public_row)
    return public_row, None, None


def _validate_inputs(manifest: Mapping[str, Any], pool: Mapping[str, Any]) -> None:
    if manifest.get("status") != "preregistered_no_outcomes":
        raise ValueError("Phase7A preregistration status mismatch")
    if manifest.get("generic_route_policy") != PHASE7A_GENERIC_ROUTE_POLICY_VERSION:
        raise ValueError("Phase7A generic route policy mismatch")
    if int(manifest.get("target_configuration_count", 0)) != int(
        pool.get("target_configuration_count", -1)
    ):
        raise ValueError("Phase7A target configuration count mismatch")
    candidates = pool.get("ordered_candidates", [])
    if not isinstance(candidates, list) or len(candidates) != len(set(candidates)):
        raise ValueError("Phase7A candidate order is invalid")
    if set(candidates) & set(pool.get("excluded_phase5_formal_scenes", [])):
        raise ValueError("Phase7A candidate pool includes a formal-v5 scene")


def qualify(
    *,
    manifest_path: Path,
    pool_path: Path,
    output_dir: Path,
    required_tag: str,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    _validate_inputs(manifest, pool)
    revision = _assert_clean_pushed_tag(required_tag)
    if output_dir.exists():
        raise ValueError("Phase7A eligibility output directory already exists")
    output_dir.mkdir(parents=True)

    from ai2thor.controller import Controller

    candidates = list(pool["ordered_candidates"])
    target_count = int(manifest["target_configuration_count"])
    max_pose_trials = int(manifest["max_pose_trials_per_scene"])
    rows: list[dict[str, Any]] = []
    selected_public: list[dict[str, Any]] = []
    selected_private: list[dict[str, Any]] = []
    route_contracts: list[dict[str, Any]] = []
    controller = Controller(scene=candidates[0], **dict(manifest["controller_settings"]))
    try:
        for candidate_index, scene in enumerate(candidates, start=1):
            if len(selected_public) >= target_count:
                break
            try:
                public, private, route = _qualify_scene(
                    controller,
                    scene,
                    manifest=manifest,
                    max_pose_trials=max_pose_trials,
                )
            except Exception as exc:
                public = {
                    "scene": scene,
                    "eligible": False,
                    "classification": "candidate_runtime_error",
                    "error_type": type(exc).__name__,
                }
                private = route = None
            public["candidate_index"] = candidate_index
            rows.append(public)
            if private is not None and route is not None:
                selected_public.append(public)
                selected_private.append(private)
                route_contracts.append(route)
            print(
                json.dumps(
                    {
                        "candidate_index": candidate_index,
                        "scene": scene,
                        "eligible": public["eligible"],
                        "classification": public["classification"],
                        "selected_count": len(selected_public),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    finally:
        controller.stop()

    private_registry: dict[str, Any] = {
        "registry_version": PHASE7A_PRIVATE_REGISTRY_VERSION,
        "boundary": PHASE7A_PRIVATE_BOUNDARY,
        "planner_visible": False,
        "included_in_planner_metrics": False,
        "configuration_count": len(selected_private),
        "configurations": selected_private,
    }
    private_registry["private_registry_digest"] = stable_digest(private_registry)
    route_registry = {
        "schema_version": SEARCH_ROUTE_SCHEMA_VERSION,
        "registry_version": PHASE7A_ROUTE_REGISTRY_VERSION,
        "route_policy": PHASE7A_GENERIC_ROUTE_POLICY_VERSION,
        "routes": route_contracts,
    }
    validate_public_artifact(route_registry)

    private_path = output_dir / "evaluator_only_holdout_registry.json"
    routes_path = output_dir / "public_holdout_routes.json"
    _write_json(private_path, private_registry)
    _write_json(routes_path, route_registry)

    passed = len(selected_public) == target_count
    public_summary = {
        "evidence_version": "phase7a-holdout-eligibility-v1",
        "code_revision": revision,
        "required_tag": required_tag,
        "ai2thor_version": _package_version("ai2thor"),
        "candidate_pool_sha256": _sha256(pool_path),
        "preregistration_manifest_sha256": _sha256(manifest_path),
        "command_used": (
            "python scripts/phase7/qualify_holdout_candidates.py "
            "--manifest configs/phase7/holdout_manifest.json "
            "--candidate-pool configs/phase7/holdout_candidate_pool.json "
            f"--output-dir {_display_path(output_dir)} --required-tag {required_tag}"
        ),
        "target_configuration_count": target_count,
        "processed_candidate_count": len(rows),
        "selected_configuration_count": len(selected_public),
        "rejected_candidate_count": sum(
            row.get("eligible") is not True for row in rows
        ),
        "passed": passed,
        "rows": rows,
        "unprocessed_after_target_reached": candidates[len(rows) :],
        "memory_variants_run": False,
        "fallback_routes_executed": False,
        "images_saved": False,
        "coordinates_exposed": False,
        "object_ids_exposed": False,
        "claim_boundary": "pre-outcome eligibility and generic route construction only; not a memory comparison or holdout outcome",
    }
    matrix_draft = {
        **manifest,
        "status": "eligibility_complete_matrix_not_frozen",
        "eligibility_evidence": "docs/evidence/phase7/holdout_eligibility_v1.json",
        "eligibility_code_revision": revision,
        "selected_configuration_count": len(selected_public),
        "selected_configurations": selected_public,
        "private_registry_digest": private_registry["private_registry_digest"],
        "evaluator_registry_sha256": _sha256(private_path),
        "route_registry_sha256": _sha256(routes_path),
        "route_registry": "configs/phase7/holdout_routes_v1.json",
        "evaluator_registry": "configs/phase7/evaluator_only/holdout_registry_v1.json",
        "outcome_execution_authorized": False,
    }
    validate_public_artifact(public_summary)
    validate_public_artifact(matrix_draft)
    _write_json(output_dir / "public_eligibility.json", public_summary)
    _write_json(output_dir / "selected_matrix_draft.json", matrix_draft)
    return public_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-pool", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--required-tag", default=DEFAULT_REQUIRED_TAG)
    args = parser.parse_args(argv)
    result = qualify(
        manifest_path=args.manifest.resolve(),
        pool_path=args.candidate_pool.resolve(),
        output_dir=args.output_dir.resolve(),
        required_tag=str(args.required_tag),
    )
    print(
        "SUMMARY "
        + json.dumps(
            {
                "passed": result["passed"],
                "processed_candidate_count": result["processed_candidate_count"],
                "selected_configuration_count": result[
                    "selected_configuration_count"
                ],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

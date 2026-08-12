#!/usr/bin/env python3
"""Pre-qualify one frozen real-THOR Book relocation anchor."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.phase4.contracts import (  # noqa: E402
    PlannerRequest,
    build_planner_observation,
)
from embodied_memory_thor.phase4.planners import (  # noqa: E402
    THOR_BOOK_ACTIONS,
    ThorBookReacquirePlanner,
    validate_planner_decision,
)
from embodied_memory_thor.phase4.runner import THOR_BOOK_SETUP_ACTIONS  # noqa: E402
from embodied_memory_thor.phase5.anchors import (  # noqa: E402
    ANCHOR_GEOMETRY_VERSION,
    ANCHOR_QUALIFICATION_VERSION,
    ANCHOR_REGISTRY_VERSION,
    BOOK_SUPPORT_TYPES,
    NATIVE_CANDIDATE_POLICY_VERSION,
    SUPPORT_POLICY_VERSION,
    build_native_first_candidate_plan,
    build_target_independent_coverage_route,
    stable_digest,
)
from embodied_memory_thor.phase5.qualification import (  # noqa: E402
    place_object_at_point_action,
    spawn_coordinate_query,
)
from embodied_memory_thor.phase5.target_lock import (  # noqa: E402
    SharedTargetLockPolicy,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


SCRIPT_VERSION = "phase5-anchor-batch-v11"
BOUNDARY = "EVALUATOR-ONLY HIDDEN STATE - NEVER PLANNER INPUT"
CONTROLLER_SETTINGS = {
    "width": 300,
    "height": 300,
    "quality": "Low",
    "gridSize": 0.25,
    "snapToGrid": True,
    "rotateStepDegrees": 90,
    "fieldOfView": 90,
    "renderDepthImage": False,
    "renderInstanceSegmentation": False,
}
MINIMUM_MOVE_METERS = 0.5
FOOTPRINT_MARGIN_METERS = 0.02
STABILITY_SAMPLE_COUNT = 3
STABILITY_TOLERANCE_METERS = 0.02
MAX_CANDIDATE_TRIALS = 12
MAX_FALLBACK_ACTIONS = 240
MAX_TARGET_LOCK_ACTIONS = 32


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _git_state() -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    return {"code_revision": revision, "working_tree_dirty": dirty}


def _objects(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = metadata.get("objects", [])
    return [obj for obj in raw if isinstance(obj, Mapping)] if isinstance(raw, list) else []


def _target(metadata: Mapping[str, Any], object_id: str) -> Mapping[str, Any] | None:
    return next((obj for obj in _objects(metadata) if obj.get("objectId") == object_id), None)


def _visible_book(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    books = sorted(
        (
            obj for obj in _objects(metadata)
            if obj.get("objectType") == "Book"
            and obj.get("pickupable") is True
            and obj.get("visible") is True
        ),
        key=lambda obj: str(obj.get("objectId", "")),
    )
    if not books:
        raise RuntimeError("no visible pickupable Book after frozen setup")
    return books[0]


def _run_setup(
    env: ThorEnv, setup_actions: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, action in enumerate(setup_actions, start=1):
        event = env.step(action)
        record = {
            "index": index,
            "action": dict(action),
            "success": bool(event.metadata.get("lastActionSuccess", False)),
            "error": str(event.metadata.get("errorMessage", "")),
        }
        records.append(record)
        if not record["success"]:
            raise RuntimeError(f"setup action failed at {index}")
    return records


def _reset_setup(
    env: ThorEnv, scene: str, setup_actions: Sequence[Mapping[str, Any]]
) -> tuple[Mapping[str, Any], list[dict[str, Any]]]:
    env.reset(scene)
    setup = _run_setup(env, setup_actions)
    return env.get_evaluator_state(), setup


def _load_candidate_contract(path: Path, scene: str) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    candidates = raw.get("candidates", []) if isinstance(raw, Mapping) else []
    matches = [
        dict(item)
        for item in candidates
        if isinstance(item, Mapping) and item.get("scene") == scene
    ]
    if len(matches) != 1:
        raise ValueError(f"candidate contract requires exactly one row for {scene}")
    return matches[0]


def _load_private_start(paths: Sequence[Path], scene: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        for row in raw.get("rows", []) if isinstance(raw, Mapping) else []:
            if not isinstance(row, Mapping) or row.get("scene") != scene:
                continue
            source = row.get("start_qualification", row)
            if not isinstance(source, Mapping) or source.get("passed", source.get("qualified")) is not True:
                continue
            pose = source.get("selected_pose")
            if isinstance(pose, Mapping):
                matches.append(
                    {
                        "scene": scene,
                        "selected_pose": dict(pose),
                        "selected_pose_digest": str(source.get("selected_pose_digest", "")),
                    }
                )
    if len(matches) != 1:
        raise ValueError(f"private start registries require exactly one passing row for {scene}")
    return matches[0]


def _setup_actions_for_candidate(
    *, scene: str, candidate_contract: Path | None,
    start_registries: Sequence[Path],
) -> tuple[
    tuple[dict[str, Any], ...], str, str, str | None, int | None, float,
    float | None,
]:
    if candidate_contract is not None:
        if not start_registries:
            raise ValueError("--candidate-contract requires at least one --start-registry")
        contract = _load_candidate_contract(candidate_contract.resolve(), scene)
        start = _load_private_start(
            [path.resolve() for path in start_registries], scene
        )
        pose = dict(start["selected_pose"])
        pose_digest = stable_digest(pose)
        if pose_digest != start["selected_pose_digest"]:
            raise ValueError("private start pose does not match its retained digest")
        if pose_digest != contract.get("start_pose_digest"):
            raise ValueError("private start pose does not match the public candidate contract")
        return (
            ({"action": "TeleportFull", **pose},),
            str(contract["configuration_id"]),
            str(contract["anchor_id"]),
            str(contract["coverage_route_digest"]),
            int(contract["coverage_route_action_count"]),
            float(contract.get("coverage_scan_horizon_degrees", 0.0)),
            (
                float(contract["absolute_scan_horizon_degrees"])
                if contract.get("absolute_scan_horizon_degrees") is not None
                else None
            ),
        )
    if scene != "FloorPlan1":
        raise ValueError("non-FloorPlan1 qualification requires frozen candidate inputs")
    return (
        tuple(dict(action) for action in THOR_BOOK_SETUP_ACTIONS),
        "FloorPlan1_R1_fixed_start_001",
        "FloorPlan1_R1_stale_Book_anchor_001",
        None,
        None,
        0.0,
        None,
    )


def _position(obj: Mapping[str, Any] | None) -> dict[str, float] | None:
    raw = obj.get("position") if isinstance(obj, Mapping) else None
    if not isinstance(raw, Mapping):
        return None
    try:
        return {axis: float(raw[axis]) for axis in ("x", "y", "z")}
    except (KeyError, TypeError, ValueError):
        return None


def _xz_distance(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["z"]) - float(b["z"]))


def _rank_supports(
    metadata: Mapping[str, Any], *, before_position: Mapping[str, Any],
    excluded_ids: Sequence[str],
) -> list[Mapping[str, Any]]:
    excluded = set(excluded_ids)
    supports = [
        obj for obj in _objects(metadata)
        if obj.get("objectType") in BOOK_SUPPORT_TYPES
        and obj.get("receptacle") is True
        and obj.get("objectId")
        and obj.get("objectId") not in excluded
        and _position(obj) is not None
    ]
    return sorted(
        supports,
        key=lambda obj: (
            -_xz_distance(before_position, _position(obj) or before_position),
            str(obj["objectId"]),
        ),
    )


def _collect_precommitted_plan(
    env: ThorEnv, *, scene: str, output_dir: Path, git_state: Mapping[str, Any],
    setup_actions: Sequence[Mapping[str, Any]], configuration_id: str,
    expected_route_digest: str | None = None,
    expected_route_action_count: int | None = None,
    coverage_scan_horizon_degrees: float = 0.0,
    absolute_scan_horizon_degrees: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Mapping[str, Any]]:
    reference_metadata, _ = _reset_setup(env, scene, setup_actions)
    reference_book = _visible_book(reference_metadata)
    before_position = _position(reference_book)
    if before_position is None:
        raise RuntimeError("Book position unavailable")
    target_id = str(reference_book["objectId"])
    parent_ids = [
        str(value) for value in reference_book.get("parentReceptacles") or []
    ]
    reference_supports = _rank_supports(
        reference_metadata,
        before_position=before_position,
        excluded_ids=parent_ids,
    )
    support_queries: list[dict[str, Any]] = []
    query_audit: list[dict[str, Any]] = []
    for rank, reference_support in enumerate(reference_supports, start=1):
        metadata, query_setup = _reset_setup(env, scene, setup_actions)
        reset_book = _visible_book(metadata)
        if str(reset_book.get("objectId", "")) != target_id:
            raise RuntimeError("target identity changed across support-query reset")
        support_id = str(reference_support["objectId"])
        support = _target(metadata, support_id)
        if (
            support is None
            or support.get("objectType") not in BOOK_SUPPORT_TYPES
            or support.get("receptacle") is not True
        ):
            raise RuntimeError("support identity changed across support-query reset")
        action = spawn_coordinate_query(str(support["objectId"]), anywhere=True)
        event = env.step(action)
        raw = event.metadata.get("actionReturn")
        coordinates = [dict(item) for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []
        query_audit.append(
            {
                "support_rank": rank,
                "support_id": str(support["objectId"]),
                "success": bool(event.metadata.get("lastActionSuccess", False)),
                "error": str(event.metadata.get("errorMessage", "")),
                "coordinate_count": len(coordinates),
                "fresh_reset_before_query": True,
                "setup_action_count": len(query_setup),
                "measured_action_count": 1,
                "query_state_reused": False,
            }
        )
        if event.metadata.get("lastActionSuccess") is True and coordinates:
            support_queries.append({"support": deepcopy(dict(support)), "coordinates": coordinates})

    # No query-mutated state is used for route construction, geometry metadata,
    # placement, or a later support query.
    metadata, setup = _reset_setup(env, scene, setup_actions)
    book = _visible_book(metadata)
    if str(book.get("objectId", "")) != target_id:
        raise RuntimeError("target identity changed before clean planning reset")
    reachable_event = env.step({"action": "GetReachablePositions"})
    reachable_raw = reachable_event.metadata.get("actionReturn")
    reachable = [dict(item) for item in reachable_raw if isinstance(item, Mapping)] if isinstance(reachable_raw, list) else []
    if reachable_event.metadata.get("lastActionSuccess") is not True or not reachable:
        raise RuntimeError("GetReachablePositions failed during coverage planning")
    agent = metadata.get("agent", {})
    coverage_route = build_target_independent_coverage_route(
        reachable_positions=reachable,
        start_position=agent.get("position", {}),
        start_yaw=float(agent.get("rotation", {}).get("y", 0.0)),
        grid_size=float(CONTROLLER_SETTINGS["gridSize"]),
        scan_horizon_degrees=coverage_scan_horizon_degrees,
        start_camera_horizon_degrees=float(agent.get("cameraHorizon", 0.0)),
        absolute_scan_horizon_degrees=absolute_scan_horizon_degrees,
    )
    if len(coverage_route["actions"]) > MAX_FALLBACK_ACTIONS:
        raise RuntimeError(
            "target-independent coverage route exceeds frozen fallback limit: "
            f"{len(coverage_route['actions'])}>{MAX_FALLBACK_ACTIONS}"
        )
    route_digest = stable_digest(coverage_route)
    if expected_route_digest and route_digest != expected_route_digest:
        raise RuntimeError(
            f"coverage route digest mismatch: {route_digest}!={expected_route_digest}"
        )
    if (
        expected_route_action_count is not None
        and len(coverage_route["actions"]) != expected_route_action_count
    ):
        raise RuntimeError(
            "coverage route action count mismatch: "
            f"{len(coverage_route['actions'])}!={expected_route_action_count}"
        )
    _write_json(output_dir / "coverage_route.json", coverage_route)

    geometry = build_native_first_candidate_plan(
        target=book,
        support_queries=support_queries,
        all_objects=_objects(metadata),
        minimum_move_meters=MINIMUM_MOVE_METERS,
        footprint_margin_meters=FOOTPRINT_MARGIN_METERS,
    )
    plan = {
        "qualification_version": ANCHOR_QUALIFICATION_VERSION,
        "geometry_version": ANCHOR_GEOMETRY_VERSION,
        "candidate_policy_version": NATIVE_CANDIDATE_POLICY_VERSION,
        "support_policy_version": SUPPORT_POLICY_VERSION,
        "script_version": SCRIPT_VERSION,
        "created_at": _utc_now(),
        "created_before_native_placement_trials": True,
        "placement_outcomes_used_for_ordering": False,
        "boundary": BOUNDARY,
        "scene": scene,
        "configuration_id": configuration_id,
        "controller_settings": CONTROLLER_SETTINGS,
        "setup_actions": setup,
        "target": {
            "object_id": str(book["objectId"]),
            "object_type": "Book",
            "before_position": before_position,
            "original_parent_ids": parent_ids,
        },
        "support_query_audit": query_audit,
        "support_query_protocol": {
            "spawn_query_anywhere": True,
            "one_support_query_per_fresh_reset": True,
            "support_query_count": len(query_audit),
            "query_state_reused_by_later_query_or_trial": False,
            "post_query_clean_reset_before_route_and_geometry": True,
            "support_policy_admission_uses_query_outcome": False,
        },
        "coverage_route_digest": route_digest,
        "coverage_route_action_count": len(coverage_route["actions"]),
        "max_fallback_actions": MAX_FALLBACK_ACTIONS,
        "coverage_scan_horizon_degrees": coverage_scan_horizon_degrees,
        "absolute_scan_horizon_degrees": absolute_scan_horizon_degrees,
        "max_candidate_trials": MAX_CANDIDATE_TRIALS,
        "stability_sample_count": STABILITY_SAMPLE_COUNT,
        "stability_tolerance_meters": STABILITY_TOLERANCE_METERS,
        "geometry": geometry,
        **dict(git_state),
    }
    plan["candidate_plan_digest"] = stable_digest(plan)
    _write_json(output_dir / "evaluator_only_candidate_plan.json", plan)
    return plan, coverage_route, book


def _aabb(obj: Mapping[str, Any]) -> tuple[float, float, float, float, float, float] | None:
    raw = obj.get("axisAlignedBoundingBox")
    center = raw.get("center") if isinstance(raw, Mapping) else None
    size = raw.get("size") if isinstance(raw, Mapping) else None
    if not isinstance(center, Mapping) or not isinstance(size, Mapping):
        return None
    try:
        return (
            float(center["x"]) - float(size["x"]) / 2,
            float(center["x"]) + float(size["x"]) / 2,
            float(center["y"]) - float(size["y"]) / 2,
            float(center["y"]) + float(size["y"]) / 2,
            float(center["z"]) - float(size["z"]) / 2,
            float(center["z"]) + float(size["z"]) / 2,
        )
    except (KeyError, TypeError, ValueError):
        return None


def _overlap_volume(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return (
        max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
        * max(0.0, min(a[3], b[3]) - max(a[2], b[2]))
        * max(0.0, min(a[5], b[5]) - max(a[4], b[4]))
    )


def _post_placement_overlap_ids(
    metadata: Mapping[str, Any], *, target_id: str, support_id: str
) -> list[str]:
    target = _target(metadata, target_id)
    target_box = _aabb(target) if target is not None else None
    if target_box is None:
        return ["__target_aabb_missing__"]
    return sorted(
        str(obj.get("objectId", ""))
        for obj in _objects(metadata)
        if str(obj.get("objectId", "")) not in {target_id, support_id}
        and (box := _aabb(obj)) is not None
        and _overlap_volume(target_box, box) > 1e-5
    )


def _physical_placement_trial(
    env: ThorEnv,
    *,
    scene: str,
    target_id: str,
    before_position: Mapping[str, Any],
    support_id: str,
    point: Mapping[str, Any],
    setup_actions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    metadata, setup = _reset_setup(env, scene, setup_actions)
    initial = _target(metadata, target_id)
    reasons: list[str] = []
    if initial is None or initial.get("visible") is not True:
        return {"passed": False, "rejection_reasons": ["reset_target_not_visible"], "setup": setup}
    action = place_object_at_point_action(target_id, point)
    event = env.step(action)
    placement_success = bool(event.metadata.get("lastActionSuccess", False))
    if not placement_success:
        reasons.append("placement_action_failed")
    immediate = _target(event.metadata, target_id)
    if immediate is None:
        reasons.append("same_target_missing_after_placement")
    immediate_position = _position(immediate)
    moved = _xz_distance(before_position, immediate_position) if immediate_position else None
    if moved is None or moved < MINIMUM_MOVE_METERS:
        reasons.append("target_position_not_materially_changed")
    if immediate is not None and immediate.get("visible") is True:
        reasons.append("target_visible_from_old_viewpoint")

    samples: list[dict[str, Any]] = []
    final_metadata = event.metadata
    for sample_index in range(1, STABILITY_SAMPLE_COUNT + 1):
        sample_event = env.step({"action": "Pass"})
        final_metadata = sample_event.metadata
        sample_target = _target(final_metadata, target_id)
        samples.append(
            {
                "sample_index": sample_index,
                "exists": sample_target is not None,
                "position": _position(sample_target),
                "is_moving": sample_target.get("isMoving") if sample_target else None,
                "visible": sample_target.get("visible") if sample_target else None,
            }
        )
    positions = [item["position"] for item in samples if item["position"] is not None]
    stable = (
        len(positions) == STABILITY_SAMPLE_COUNT
        and all(_xz_distance(positions[0], item) <= STABILITY_TOLERANCE_METERS for item in positions[1:])
        and all(item["is_moving"] is False for item in samples)
    )
    if not stable:
        reasons.append("target_not_stable")
    final_target = _target(final_metadata, target_id)
    parents = [str(value) for value in (final_target.get("parentReceptacles") or [])] if final_target else []
    if support_id not in parents:
        reasons.append("expected_support_relation_missing")
    overlaps = _post_placement_overlap_ids(
        final_metadata, target_id=target_id, support_id=support_id
    )
    if overlaps:
        reasons.append("post_placement_non_support_overlap")
    return {
        "passed": not reasons,
        "rejection_reasons": reasons,
        "setup": setup,
        "placement_action": action,
        "placement_success": placement_success,
        "placement_error": str(event.metadata.get("errorMessage", "")),
        "same_target_exists": immediate is not None,
        "moved_distance_xz_meters": moved,
        "old_view_invisible": immediate is not None and immediate.get("visible") is False,
        "stability_samples": samples,
        "stable": stable,
        "final_parent_ids": parents,
        "post_placement_overlap_ids": overlaps,
    }


def _picked_up(metadata: Mapping[str, Any], target_id: str) -> bool:
    inventory = metadata.get("inventoryObjects", [])
    if isinstance(inventory, list) and any(
        isinstance(item, Mapping) and item.get("objectId") == target_id for item in inventory
    ):
        return True
    target = _target(metadata, target_id)
    return target is not None and target.get("isPickedUp") is True


def _fallback_rediscovery_audit(
    env: ThorEnv, *, target_id: str, coverage_route: Mapping[str, Any]
) -> dict[str, Any]:
    action_log: list[dict[str, Any]] = []
    route_actions = coverage_route.get("actions", [])
    route_cursor = 0
    target_lock_action_count = 0
    planner = ThorBookReacquirePlanner()
    target_lock = SharedTargetLockPolicy(target_type="Book")
    recent: list[dict[str, Any]] = []
    discovery_step: int | None = None
    while route_cursor < min(len(route_actions), MAX_FALLBACK_ACTIONS):
        observation = build_planner_observation(env.get_observation())
        directive = target_lock.next_directive(
            observation,
            allowed_actions=THOR_BOOK_ACTIONS,
        )
        if directive is not None:
            target_lock_action_count += 1
            if target_lock_action_count > MAX_TARGET_LOCK_ACTIONS:
                return {
                    "passed": False,
                    "reason": "target_lock_total_action_limit_exceeded",
                    "discovery_step": discovery_step,
                    "action_log": action_log,
                    **target_lock.snapshot(),
                }
            if discovery_step is None:
                discovery_step = route_cursor
            request = PlannerRequest(
                task_name="thor_book_reacquire_k2",
                instruction="Reacquire and pick up the Book.",
                task_stage=(
                    "pickup_book"
                    if any(
                        isinstance(obj, Mapping)
                        and obj.get("objectType") == "Book"
                        and obj.get("visible") is True
                        for obj in observation.get("objects", [])
                    )
                    else "reacquire_book"
                ),
                step=len(action_log) + 1,
                max_steps=MAX_FALLBACK_ACTIONS + MAX_TARGET_LOCK_ACTIONS,
                observation=observation,
                allowed_actions=THOR_BOOK_ACTIONS,
                retrieved_memory=(),
                recent_action_results=tuple(recent[-5:]),
                target_lock=directive,
            )
            decision = planner.plan(request)
            valid, errors = validate_planner_decision(decision, request)
            if not valid:
                return {
                    "passed": False,
                    "reason": "target_lock_decision_invalid:" + ";".join(errors),
                    "discovery_step": discovery_step,
                    "action_log": action_log,
                    **target_lock.snapshot(),
                }
            event = env.step(decision.action)
            success = bool(event.metadata.get("lastActionSuccess", False))
            post_observation = build_planner_observation(env.get_observation())
            target_lock.record_result(
                directive,
                success=success,
                error_message=str(event.metadata.get("errorMessage", "")),
                observation_after=post_observation,
                allowed_actions=THOR_BOOK_ACTIONS,
            )
            record = {
                "step": len(action_log) + 1,
                "action": dict(decision.action),
                "reason_code": decision.reason_code,
                "success": success,
                "error": str(event.metadata.get("errorMessage", "")),
            }
            action_log.append(record)
            recent.append(record)
            if _picked_up(event.metadata, target_id):
                return {
                    "passed": True,
                    "reason": "",
                    "discovery_step": discovery_step,
                    "pickup_step": len(action_log),
                    "action_log": action_log,
                    **target_lock.snapshot(),
                }
            if (
                target_lock.metrics.target_lock_failed_reason
                and not target_lock.active
            ):
                return {
                    "passed": False,
                    "reason": (
                        "target_lock_failed:"
                        + target_lock.metrics.target_lock_failed_reason
                    ),
                    "discovery_step": discovery_step,
                    "action_log": action_log,
                    **target_lock.snapshot(),
                }
            continue

        row = route_actions[route_cursor]
        route_cursor += 1
        action = dict(row["action"])
        event = env.step(action)
        success = bool(event.metadata.get("lastActionSuccess", False))
        action_log.append(
            {
                "step": len(action_log) + 1,
                "action": action,
                "route_phase": row.get("phase"),
                "success": success,
                "error": str(event.metadata.get("errorMessage", "")),
            }
        )
        if not success:
            return {
                "passed": False,
                "reason": "coverage_route_action_failed",
                "discovery_step": None,
                "action_log": action_log,
                **target_lock.snapshot(),
            }
    return {
        "passed": False,
        "reason": "target_not_rediscovered_within_fallback_limit",
        "discovery_step": discovery_step,
        "action_log": action_log,
        **target_lock.snapshot(),
    }


def _reset_restoration_check(
    env: ThorEnv, *, scene: str, target_id: str, before_position: Mapping[str, Any],
    setup_actions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    metadata, setup = _reset_setup(env, scene, setup_actions)
    target = _target(metadata, target_id)
    position = _position(target)
    delta = _xz_distance(before_position, position) if position else None
    passed = (
        target is not None
        and target.get("visible") is True
        and delta is not None
        and delta <= STABILITY_TOLERANCE_METERS
    )
    return {
        "passed": passed,
        "setup": setup,
        "same_target_exists": target is not None,
        "target_visible": target.get("visible") if target else None,
        "position_delta_xz_meters": delta,
    }


def _aggregate_target_lock_metrics(
    trial_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    audits = [
        row.get("common_fallback_audit", {})
        for row in trial_records
        if isinstance(row, Mapping)
        and isinstance(row.get("common_fallback_audit", {}), Mapping)
    ]
    numeric_fields = (
        "target_visible_event_count",
        "target_lock_entered_count",
        "target_lock_pickup_attempt_count",
        "transient_visibility_loss_count",
        "local_recovery_action_count",
        "target_reacquired_after_loss_count",
    )
    reasons = sorted(
        {
            str(audit.get("target_lock_failed_reason", ""))
            for audit in audits
            if str(audit.get("target_lock_failed_reason", ""))
        }
    )
    return {
        field: sum(
            int(audit.get(field, 0))
            for audit in audits
            if isinstance(audit.get(field, 0), (int, bool))
        )
        for field in numeric_fields
    } | {
        "picked_after_target_lock": any(
            audit.get("picked_after_target_lock") is True for audit in audits
        ),
        "target_lock_failed_reason": ";".join(reasons),
    }


def _select_candidate_trials(
    candidates: Sequence[Mapping[str, Any]],
    *,
    diagnostic_candidate_order: int | None,
) -> list[Mapping[str, Any]]:
    """Select the frozen batch prefix or exactly one diagnostic candidate."""

    frozen_prefix = list(candidates[:MAX_CANDIDATE_TRIALS])
    if diagnostic_candidate_order is None:
        return frozen_prefix
    if diagnostic_candidate_order < 1:
        raise ValueError("diagnostic candidate order must be positive")
    selected = [
        row
        for row in frozen_prefix
        if row.get("candidate_order") == diagnostic_candidate_order
    ]
    if len(selected) != 1:
        raise ValueError(
            "diagnostic candidate order must identify exactly one candidate "
            f"within the frozen first {MAX_CANDIDATE_TRIALS}"
        )
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="FloorPlan1")
    parser.add_argument("--output-dir")
    parser.add_argument("--candidate-contract", type=Path)
    parser.add_argument("--start-registry", type=Path, action="append", default=[])
    parser.add_argument(
        "--diagnostic-candidate-order",
        type=int,
        help=(
            "Run exactly one frozen candidate as target-lock diagnostic QA; "
            "does not freeze an anchor or perform fresh-reset replay."
        ),
    )
    parser.add_argument(
        "--coverage-scan-horizon-degrees",
        type=float,
        choices=(0.0, 30.0),
        help=(
            "Target-independent coverage camera horizon. Candidate contracts "
            "bind this value; omit the flag to use the contract."
        ),
    )
    args = parser.parse_args(argv)
    diagnostic_mode = args.diagnostic_candidate_order is not None
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else PROJECT_ROOT
        / "outputs"
        / (
            "phase5_target_lock_diagnostic"
            if diagnostic_mode
            else "phase5_anchor_qualification"
        )
        / _slug()
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    git_state = _git_state()
    if git_state["working_tree_dirty"] is not False:
        summary = {
            "passed": False,
            "reason": "clean_worktree_required",
            "output_dir": str(output_dir),
        }
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 2

    (
        setup_actions,
        configuration_id,
        anchor_id,
        expected_route_digest,
        expected_route_action_count,
        contracted_scan_horizon_degrees,
        contracted_absolute_scan_horizon_degrees,
    ) = _setup_actions_for_candidate(
        scene=args.scene,
        candidate_contract=args.candidate_contract,
        start_registries=args.start_registry,
    )
    if (
        args.coverage_scan_horizon_degrees is not None
        and args.coverage_scan_horizon_degrees
        != contracted_scan_horizon_degrees
    ):
        raise ValueError(
            "coverage scan horizon does not match the candidate contract"
        )
    coverage_scan_horizon_degrees = contracted_scan_horizon_degrees
    absolute_scan_horizon_degrees = contracted_absolute_scan_horizon_degrees

    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    trial_records: list[dict[str, Any]] = []
    primary_anchor: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    route: dict[str, Any] | None = None
    fatal_error = ""
    diagnostic_passed = False
    try:
        plan, route, _ = _collect_precommitted_plan(
            env, scene=args.scene, output_dir=output_dir, git_state=git_state,
            setup_actions=setup_actions, configuration_id=configuration_id,
            expected_route_digest=expected_route_digest,
            expected_route_action_count=expected_route_action_count,
            coverage_scan_horizon_degrees=coverage_scan_horizon_degrees,
            absolute_scan_horizon_degrees=absolute_scan_horizon_degrees,
        )
        target_id = str(plan["target"]["object_id"])
        before_position = dict(plan["target"]["before_position"])
        candidates = _select_candidate_trials(
            plan["geometry"]["accepted_candidates"],
            diagnostic_candidate_order=args.diagnostic_candidate_order,
        )
        for candidate in candidates:
            candidate_record: dict[str, Any] = {
                "candidate_order": candidate["candidate_order"],
                "support_id": candidate["support_id"],
                "point": deepcopy(candidate["point"]),
                "boundary": BOUNDARY,
            }
            first = _physical_placement_trial(
                env,
                scene=args.scene,
                target_id=target_id,
                before_position=before_position,
                support_id=str(candidate["support_id"]),
                point=candidate["point"],
                setup_actions=setup_actions,
            )
            candidate_record["first_physical_trial"] = first
            if first["passed"]:
                fallback = _fallback_rediscovery_audit(
                    env, target_id=target_id, coverage_route=route
                )
            else:
                fallback = {"passed": False, "reason": "skipped_after_physical_failure"}
            candidate_record["common_fallback_audit"] = fallback

            if diagnostic_mode:
                replay = {
                    "passed": False,
                    "skipped": True,
                    "reason": "single_probe_does_not_run_fresh_reset_replay",
                }
            elif first["passed"] and fallback["passed"]:
                replay = _physical_placement_trial(
                    env,
                    scene=args.scene,
                    target_id=target_id,
                    before_position=before_position,
                    support_id=str(candidate["support_id"]),
                    point=candidate["point"],
                    setup_actions=setup_actions,
                )
            else:
                replay = {"passed": False, "rejection_reasons": ["skipped_after_prior_failure"]}
            candidate_record["fresh_reset_replay"] = replay
            restoration = _reset_restoration_check(
                env,
                scene=args.scene,
                target_id=target_id,
                before_position=before_position,
                setup_actions=setup_actions,
            )
            candidate_record["reset_restoration"] = restoration
            passed = bool(
                first["passed"]
                and fallback["passed"]
                and restoration["passed"]
                and (diagnostic_mode or replay["passed"])
            )
            candidate_record["passed"] = passed
            rejection_reasons = list(first.get("rejection_reasons", []))
            if not fallback["passed"]:
                rejection_reasons.append(str(fallback.get("reason", "fallback_failed")))
            if not diagnostic_mode:
                rejection_reasons.extend(replay.get("rejection_reasons", []))
            if not restoration["passed"]:
                rejection_reasons.append("reset_restoration_failed")
            candidate_record["rejection_reasons"] = rejection_reasons
            trial_records.append(candidate_record)
            if diagnostic_mode:
                diagnostic_passed = passed
                break
            if passed:
                primary_anchor = {
                    "anchor_id": anchor_id,
                    "configuration_id": plan["configuration_id"],
                    "scene": args.scene,
                    "target_object_id": target_id,
                    "target_object_type": "Book",
                    "support_id": candidate["support_id"],
                    "target_point": deepcopy(candidate["point"]),
                    "candidate_order": candidate["candidate_order"],
                    "intervention_milestone": "after_controlled_distraction_3",
                    "candidate_plan_digest": plan["candidate_plan_digest"],
                    "coverage_route_digest": plan["coverage_route_digest"],
                    "qualification_evidence": deepcopy(candidate_record),
                }
                break
    except Exception as exc:
        fatal_error = f"{type(exc).__name__}: {exc}"
    finally:
        env.close()

    registry = {
        "registry_version": ANCHOR_REGISTRY_VERSION,
        "qualification_version": ANCHOR_QUALIFICATION_VERSION,
        "geometry_version": ANCHOR_GEOMETRY_VERSION,
        "candidate_policy_version": NATIVE_CANDIDATE_POLICY_VERSION,
        "support_policy_version": SUPPORT_POLICY_VERSION,
        "created_at": _utc_now(),
        "boundary": BOUNDARY,
        "planner_visible": False,
        "included_in_planner_metrics": False,
        "script_version": SCRIPT_VERSION,
        "scene": args.scene,
        "controller_settings": CONTROLLER_SETTINGS,
        "ai2thor_version": _package_version("ai2thor"),
        "images_saved": False,
        "candidate_plan_digest": plan.get("candidate_plan_digest") if plan else None,
        "coverage_route_digest": plan.get("coverage_route_digest") if plan else None,
        "coverage_route_version": route.get("route_version") if route else None,
        "coverage_route_action_count": len(route.get("actions", [])) if route else None,
        "coverage_scan_horizon_degrees": coverage_scan_horizon_degrees,
        "absolute_scan_horizon_degrees": absolute_scan_horizon_degrees,
        "candidate_trial_records": trial_records,
        "diagnostic_mode": diagnostic_mode,
        "diagnostic_candidate_order": args.diagnostic_candidate_order,
        "anchor_freezing_allowed": not diagnostic_mode,
        "anchors": [primary_anchor] if primary_anchor and not diagnostic_mode else [],
        "fatal_error": fatal_error,
        **git_state,
    }
    registry_digest = stable_digest(registry)
    registry["private_registry_digest"] = registry_digest
    registry_path = output_dir / (
        "evaluator_only_target_lock_diagnostic.json"
        if diagnostic_mode
        else "evaluator_only_anchor_registry.json"
    )
    _write_json(registry_path, registry)
    passed = (
        diagnostic_passed and not fatal_error
        if diagnostic_mode
        else primary_anchor is not None and not fatal_error
    )
    target_lock_metrics = _aggregate_target_lock_metrics(trial_records)
    summary = {
        "qualification_version": ANCHOR_QUALIFICATION_VERSION,
        "geometry_version": ANCHOR_GEOMETRY_VERSION,
        "candidate_policy_version": NATIVE_CANDIDATE_POLICY_VERSION,
        "support_policy_version": SUPPORT_POLICY_VERSION,
        "claim": (
            "single-candidate target-lock diagnostic; not anchor qualification "
            "or a memory comparison"
            if diagnostic_mode
            else "pre-qualified relocation anchor QA; not a memory comparison"
        ),
        "scene": args.scene,
        "passed": passed,
        "diagnostic_mode": diagnostic_mode,
        "diagnostic_candidate_order": args.diagnostic_candidate_order,
        "memory_agents_run": False,
        "anchor_frozen": primary_anchor is not None and not diagnostic_mode,
        "anchor_id": (
            primary_anchor["anchor_id"]
            if primary_anchor is not None and not diagnostic_mode
            else None
        ),
        "candidate_plan_digest": plan.get("candidate_plan_digest") if plan else None,
        "coverage_route_digest": plan.get("coverage_route_digest") if plan else None,
        "coverage_route_version": route.get("route_version") if route else None,
        "coverage_route_action_count": len(route.get("actions", [])) if route else None,
        "coverage_scan_horizon_degrees": coverage_scan_horizon_degrees,
        "absolute_scan_horizon_degrees": absolute_scan_horizon_degrees,
        "private_registry_digest": registry_digest,
        "candidate_trial_count": len(trial_records),
        "fatal_error": fatal_error,
        "images_saved": False,
        "coordinates_exposed_in_summary": False,
        **target_lock_metrics,
        "private_registry": str(registry_path),
        "output_dir": str(output_dir),
        "finished_at": _utc_now(),
    }
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

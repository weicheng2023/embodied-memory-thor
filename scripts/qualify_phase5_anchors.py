#!/usr/bin/env python3
"""Pre-qualify one frozen FloorPlan1 Book relocation anchor."""

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
    ANCHOR_QUALIFICATION_VERSION,
    ANCHOR_REGISTRY_VERSION,
    OPEN_SUPPORT_TYPES,
    build_geometry_candidate_plan,
    build_target_independent_coverage_route,
    stable_digest,
)
from embodied_memory_thor.phase5.qualification import (  # noqa: E402
    place_object_at_point_action,
    spawn_coordinate_query,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


SCRIPT_VERSION = "phase5-anchor-batch-v3"
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
MAX_VISIBLE_INTERACTION_ACTIONS = 20


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


def _run_setup(env: ThorEnv) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, action in enumerate(THOR_BOOK_SETUP_ACTIONS, start=1):
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


def _reset_setup(env: ThorEnv, scene: str) -> tuple[Mapping[str, Any], list[dict[str, Any]]]:
    env.reset(scene)
    setup = _run_setup(env)
    return env.get_evaluator_state(), setup


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
        if obj.get("objectType") in OPEN_SUPPORT_TYPES
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
    env: ThorEnv, *, scene: str, output_dir: Path, git_state: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], Mapping[str, Any]]:
    metadata, setup = _reset_setup(env, scene)
    book = _visible_book(metadata)
    before_position = _position(book)
    if before_position is None:
        raise RuntimeError("Book position unavailable")
    parent_ids = [str(value) for value in book.get("parentReceptacles") or []]
    supports = _rank_supports(
        metadata, before_position=before_position, excluded_ids=parent_ids
    )
    support_queries: list[dict[str, Any]] = []
    query_audit: list[dict[str, Any]] = []
    for rank, support in enumerate(supports, start=1):
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
            }
        )
        if event.metadata.get("lastActionSuccess") is True and coordinates:
            support_queries.append({"support": deepcopy(dict(support)), "coordinates": coordinates})

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
    )
    if len(coverage_route["actions"]) > MAX_FALLBACK_ACTIONS:
        raise RuntimeError(
            "target-independent coverage route exceeds frozen fallback limit: "
            f"{len(coverage_route['actions'])}>{MAX_FALLBACK_ACTIONS}"
        )
    route_digest = stable_digest(coverage_route)
    _write_json(output_dir / "coverage_route.json", coverage_route)

    geometry = build_geometry_candidate_plan(
        target=book,
        support_queries=support_queries,
        all_objects=_objects(metadata),
        minimum_move_meters=MINIMUM_MOVE_METERS,
        footprint_margin_meters=FOOTPRINT_MARGIN_METERS,
    )
    plan = {
        "qualification_version": ANCHOR_QUALIFICATION_VERSION,
        "script_version": SCRIPT_VERSION,
        "created_at": _utc_now(),
        "created_before_native_placement_trials": True,
        "placement_outcomes_used_for_ordering": False,
        "boundary": BOUNDARY,
        "scene": scene,
        "configuration_id": "FloorPlan1_R1_fixed_start_001",
        "controller_settings": CONTROLLER_SETTINGS,
        "setup_actions": setup,
        "target": {
            "object_id": str(book["objectId"]),
            "object_type": "Book",
            "before_position": before_position,
            "original_parent_ids": parent_ids,
        },
        "support_query_audit": query_audit,
        "coverage_route_digest": route_digest,
        "coverage_route_action_count": len(coverage_route["actions"]),
        "max_fallback_actions": MAX_FALLBACK_ACTIONS,
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
) -> dict[str, Any]:
    metadata, setup = _reset_setup(env, scene)
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
    discovery_step: int | None = None
    route_actions = coverage_route.get("actions", [])
    for index, row in enumerate(route_actions[:MAX_FALLBACK_ACTIONS], start=1):
        action = dict(row["action"])
        event = env.step(action)
        success = bool(event.metadata.get("lastActionSuccess", False))
        action_log.append(
            {
                "step": index,
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
            }
        visible = _target(event.metadata, target_id)
        if visible is not None and visible.get("visible") is True:
            discovery_step = index
            break
    if discovery_step is None:
        return {
            "passed": False,
            "reason": "target_not_rediscovered_within_fallback_limit",
            "discovery_step": None,
            "action_log": action_log,
        }

    planner = ThorBookReacquirePlanner()
    recent: list[dict[str, Any]] = []
    for interaction_index in range(1, MAX_VISIBLE_INTERACTION_ACTIONS + 1):
        observation = build_planner_observation(env.get_observation())
        target_visible = any(
            isinstance(obj, Mapping)
            and obj.get("objectId") == target_id
            and obj.get("visible") is True
            for obj in observation.get("objects", [])
        )
        request = PlannerRequest(
            task_name="thor_book_reacquire_k2",
            instruction="Reacquire and pick up the Book.",
            task_stage="pickup_book" if target_visible else "reacquire_book",
            step=discovery_step + interaction_index,
            max_steps=MAX_FALLBACK_ACTIONS + MAX_VISIBLE_INTERACTION_ACTIONS,
            observation=observation,
            allowed_actions=THOR_BOOK_ACTIONS,
            retrieved_memory=(),
            recent_action_results=tuple(recent[-5:]),
        )
        decision = planner.plan(request)
        valid, errors = validate_planner_decision(decision, request)
        if not valid:
            return {
                "passed": False,
                "reason": "visible_interaction_decision_invalid:" + ";".join(errors),
                "discovery_step": discovery_step,
                "action_log": action_log,
            }
        event = env.step(decision.action)
        record = {
            "step": discovery_step + interaction_index,
            "action": dict(decision.action),
            "reason_code": decision.reason_code,
            "success": bool(event.metadata.get("lastActionSuccess", False)),
            "error": str(event.metadata.get("errorMessage", "")),
        }
        action_log.append(record)
        recent.append(record)
        if _picked_up(event.metadata, target_id):
            return {
                "passed": True,
                "reason": "",
                "discovery_step": discovery_step,
                "pickup_step": discovery_step + interaction_index,
                "action_log": action_log,
            }
    return {
        "passed": False,
        "reason": "visible_target_not_picked_within_interaction_limit",
        "discovery_step": discovery_step,
        "action_log": action_log,
    }


def _reset_restoration_check(
    env: ThorEnv, *, scene: str, target_id: str, before_position: Mapping[str, Any]
) -> dict[str, Any]:
    metadata, setup = _reset_setup(env, scene)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="FloorPlan1")
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else PROJECT_ROOT / "outputs" / "phase5_anchor_qualification" / _slug()
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

    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    trial_records: list[dict[str, Any]] = []
    primary_anchor: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    route: dict[str, Any] | None = None
    fatal_error = ""
    try:
        plan, route, _ = _collect_precommitted_plan(
            env, scene=args.scene, output_dir=output_dir, git_state=git_state
        )
        target_id = str(plan["target"]["object_id"])
        before_position = dict(plan["target"]["before_position"])
        candidates = plan["geometry"]["accepted_candidates"][:MAX_CANDIDATE_TRIALS]
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
            )
            candidate_record["first_physical_trial"] = first
            if first["passed"]:
                fallback = _fallback_rediscovery_audit(
                    env, target_id=target_id, coverage_route=route
                )
            else:
                fallback = {"passed": False, "reason": "skipped_after_physical_failure"}
            candidate_record["common_fallback_audit"] = fallback

            if first["passed"] and fallback["passed"]:
                replay = _physical_placement_trial(
                    env,
                    scene=args.scene,
                    target_id=target_id,
                    before_position=before_position,
                    support_id=str(candidate["support_id"]),
                    point=candidate["point"],
                )
            else:
                replay = {"passed": False, "rejection_reasons": ["skipped_after_prior_failure"]}
            candidate_record["fresh_reset_replay"] = replay
            restoration = _reset_restoration_check(
                env,
                scene=args.scene,
                target_id=target_id,
                before_position=before_position,
            )
            candidate_record["reset_restoration"] = restoration
            passed = bool(
                first["passed"] and fallback["passed"] and replay["passed"] and restoration["passed"]
            )
            candidate_record["passed"] = passed
            rejection_reasons = list(first.get("rejection_reasons", []))
            if not fallback["passed"]:
                rejection_reasons.append(str(fallback.get("reason", "fallback_failed")))
            rejection_reasons.extend(replay.get("rejection_reasons", []))
            if not restoration["passed"]:
                rejection_reasons.append("reset_restoration_failed")
            candidate_record["rejection_reasons"] = rejection_reasons
            trial_records.append(candidate_record)
            if passed:
                primary_anchor = {
                    "anchor_id": "FloorPlan1_R1_stale_Book_anchor_001",
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
        "candidate_trial_records": trial_records,
        "anchors": [primary_anchor] if primary_anchor else [],
        "fatal_error": fatal_error,
        **git_state,
    }
    registry_digest = stable_digest(registry)
    registry["private_registry_digest"] = registry_digest
    registry_path = output_dir / "evaluator_only_anchor_registry.json"
    _write_json(registry_path, registry)
    passed = primary_anchor is not None and not fatal_error
    summary = {
        "qualification_version": ANCHOR_QUALIFICATION_VERSION,
        "claim": "pre-qualified relocation anchor QA; not a memory comparison",
        "scene": args.scene,
        "passed": passed,
        "anchor_id": primary_anchor["anchor_id"] if primary_anchor else None,
        "candidate_plan_digest": plan.get("candidate_plan_digest") if plan else None,
        "coverage_route_digest": plan.get("coverage_route_digest") if plan else None,
        "private_registry_digest": registry_digest,
        "candidate_trial_count": len(trial_records),
        "fatal_error": fatal_error,
        "images_saved": False,
        "coordinates_exposed_in_summary": False,
        "private_registry": str(registry_path),
        "output_dir": str(output_dir),
        "finished_at": _utc_now(),
    }
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

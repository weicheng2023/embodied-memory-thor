#!/usr/bin/env python3
"""Run one read-only, coordinate-free Phase 5 R1 support-type census."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.env import ThorEnv  # noqa: E402
from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.phase5.qualification import (  # noqa: E402
    spawn_coordinate_query,
)
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


SCRIPT_VERSION = "phase5-r1-support-census-script-v1"
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
ALLOWED_ENV_ACTIONS = frozenset(
    {"GetReachablePositions", "GetSpawnCoordinatesAboveReceptacle"}
)
PUBLIC_FORBIDDEN_KEYS = frozenset(
    {"objectId", "x", "y", "z", "position", "rotation", "target_point"}
)
PUBLIC_FORBIDDEN_TEXT = (
    "private_registry",
    "PlaceObjectAtPoint",
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _git_state() -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
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
    return {"code_revision": revision, "working_tree_dirty": dirty}


def load_census_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("support census config must be an object")
    scenes = raw.get("inspected_scenes")
    support_rows = raw.get("candidate_receptacle_types")
    if not isinstance(scenes, list) or len(scenes) != 6:
        raise ValueError("support census requires the frozen six scenes")
    if len(set(str(scene) for scene in scenes)) != len(scenes):
        raise ValueError("support census scenes must be unique")
    if not isinstance(support_rows, list) or not support_rows:
        raise ValueError("candidate receptacle types must be non-empty")
    support_types = [str(row.get("support_type", "")) for row in support_rows]
    if any(not value for value in support_types) or support_types != sorted(support_types):
        raise ValueError("support types must be unique and lexicographically ordered")
    if len(set(support_types)) != len(support_types):
        raise ValueError("support types must be unique and lexicographically ordered")
    required = {
        "Desk",
        "Dresser",
        "SideTable",
        "CoffeeTable",
        "DiningTable",
        "CounterTop",
        "Bed",
        "Shelf",
    }
    if not required.issubset(support_types):
        raise ValueError("support census omits required candidate types")
    constraints = raw.get("execution_constraints", {})
    if not isinstance(constraints, Mapping) or any(
        constraints.get(key) is not False
        for key in (
            "placement_actions_allowed",
            "pickup_actions_allowed",
            "fallback_route_allowed",
            "memory_agents_allowed",
            "images_allowed",
            "force_action_allowed",
        )
    ):
        raise ValueError("support census execution constraints are not read-only")
    return deepcopy(dict(raw))


def _objects(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = metadata.get("objects", [])
    return [dict(row) for row in raw if isinstance(row, Mapping)] if isinstance(raw, list) else []


def _state_digest(metadata: Mapping[str, Any]) -> str:
    """Hash exact evaluator state in memory without writing it to either output."""

    retained: list[dict[str, Any]] = []
    for obj in _objects(metadata):
        retained.append(
            {
                "objectId": obj.get("objectId"),
                "position": obj.get("position"),
                "rotation": obj.get("rotation"),
                "parentReceptacles": obj.get("parentReceptacles"),
                "isMoving": obj.get("isMoving"),
                "isPickedUp": obj.get("isPickedUp"),
                "isOpen": obj.get("isOpen"),
                "isToggled": obj.get("isToggled"),
                "isBroken": obj.get("isBroken"),
                "isDirty": obj.get("isDirty"),
                "isFilledWithLiquid": obj.get("isFilledWithLiquid"),
            }
        )
    retained.sort(key=lambda row: str(row.get("objectId", "")))
    return stable_digest(retained)


def _query_result(event: Any) -> tuple[bool, int, str]:
    metadata = getattr(event, "metadata", {})
    if not isinstance(metadata, Mapping):
        return False, 0, "metadata_unavailable"
    if metadata.get("lastActionSuccess") is not True:
        return False, 0, "action_failed"
    returned = metadata.get("actionReturn")
    if not isinstance(returned, list):
        return False, 0, "invalid_action_return"
    if not returned:
        return True, 0, "empty_action_return"
    return True, len(returned), ""


def census_scene(
    env: ThorEnv,
    *,
    scene: str,
    support_types: Sequence[str],
) -> dict[str, Any]:
    action_names: list[str] = []
    reset_event = env.reset(scene)
    reset_metadata = getattr(reset_event, "metadata", {})
    if not isinstance(reset_metadata, Mapping):
        raise RuntimeError("scene reset returned no metadata")

    reachable_action = "GetReachablePositions"
    if reachable_action not in ALLOWED_ENV_ACTIONS:
        raise RuntimeError("unapproved census action")
    reachable_event = env.step({"action": reachable_action})
    action_names.append(reachable_action)
    reachable_metadata = getattr(reachable_event, "metadata", {})
    reachable_raw = (
        reachable_metadata.get("actionReturn")
        if isinstance(reachable_metadata, Mapping)
        else None
    )
    reachable_count = len(reachable_raw) if isinstance(reachable_raw, list) else 0
    reachable_success = bool(
        isinstance(reachable_metadata, Mapping)
        and reachable_metadata.get("lastActionSuccess") is True
        and reachable_count > 0
    )
    metadata = env.get_evaluator_state()
    objects = _objects(metadata)
    before_digest = _state_digest(metadata)
    pickupable_book_count = sum(
        row.get("objectType") == "Book" and row.get("pickupable") is True
        for row in objects
    )

    support_rows: list[dict[str, Any]] = []
    for support_type in support_types:
        typed = [row for row in objects if row.get("objectType") == support_type]
        receptacles = [row for row in typed if row.get("receptacle") is True]
        query_success_count = 0
        positive_query_count = 0
        spawn_count = 0
        errors: Counter[str] = Counter()
        for support in receptacles:
            query = spawn_coordinate_query(str(support.get("objectId", "")))
            action_name = str(query.get("action", ""))
            if action_name not in ALLOWED_ENV_ACTIONS:
                raise RuntimeError("unapproved census action")
            event = env.step(query)
            action_names.append(action_name)
            success, coordinate_count, error_type = _query_result(event)
            query_success_count += int(success)
            positive_query_count += int(success and coordinate_count > 0)
            spawn_count += coordinate_count
            if error_type:
                errors[error_type] += 1
        support_rows.append(
            {
                "support_type": support_type,
                "metadata_count": len(typed),
                "receptacle_true_count": len(receptacles),
                "visible_receptacle_count": sum(
                    row.get("visible") is True for row in receptacles
                ),
                "nonvisible_receptacle_count": sum(
                    row.get("visible") is not True for row in receptacles
                ),
                "spawn_query_attempt_count": len(receptacles),
                "spawn_query_success_count": query_success_count,
                "positive_spawn_query_count": positive_query_count,
                "spawn_coordinate_count": spawn_count,
                "error_type_summary": dict(sorted(errors.items())),
            }
        )

    after_digest = _state_digest(env.get_evaluator_state())
    state_unchanged = before_digest == after_digest
    return {
        "scene": scene,
        "reset_success": True,
        "reachable_query_success": reachable_success,
        "reachable_count": reachable_count,
        "pickupable_book_count": pickupable_book_count,
        "support_types": support_rows,
        "state_unchanged_after_spawn_queries": state_unchanged,
        "last_action_isolated_by_next_scene_reset": True,
        "allowed_action_count": len(action_names),
        "unexpected_action_count": sum(
            action not in ALLOWED_ENV_ACTIONS for action in action_names
        ),
        "private_state_digest_before": before_digest,
        "private_state_digest_after": after_digest,
    }


def build_policy_candidate(
    config: Mapping[str, Any], scene_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    rule = config["support_policy_candidate_rule"]
    minimum_presence = int(rule["minimum_receptacle_presence_scenes"])
    minimum_positive = int(rule["minimum_positive_spawn_scenes"])
    admitted: list[str] = []
    exclusions: list[dict[str, str]] = []
    for declared in config["candidate_receptacle_types"]:
        support_type = str(declared["support_type"])
        rows = [
            next(
                row
                for row in scene["support_types"]
                if row["support_type"] == support_type
            )
            for scene in scene_rows
        ]
        presence_scenes = sum(row["receptacle_true_count"] > 0 for row in rows)
        positive_scenes = sum(row["positive_spawn_query_count"] > 0 for row in rows)
        semantic = declared.get("semantic_book_support_candidate") is True
        if semantic and presence_scenes >= minimum_presence and positive_scenes >= minimum_positive:
            admitted.append(support_type)
        else:
            reasons: list[str] = []
            if not semantic:
                reasons.append("not_predeclared_as_semantic_book_support")
            if presence_scenes < minimum_presence:
                reasons.append("too_rare_in_inspected_scenes")
            if positive_scenes < minimum_positive:
                reasons.append("no_positive_read_only_spawn_query")
            exclusions.append(
                {"support_type": support_type, "reason": "+".join(reasons)}
            )
    return {
        "policy_version": rule["policy_version"],
        "selection_rule": rule["selection_rule"],
        "admitted_support_types": admitted,
        "exclusions": exclusions,
        "placement_outcomes_used": False,
        "safety_margin_meters": rule["safety_margin_meters"],
        "route_version": rule["route_version"],
        "formal_use_allowed": False,
    }


def build_public_summary(
    *,
    config: Mapping[str, Any],
    raw_scene_rows: Sequence[Mapping[str, Any]],
    git_state: Mapping[str, Any],
    raw_digest: str,
    fatal_error_category: str = "",
) -> dict[str, Any]:
    scene_rows: list[dict[str, Any]] = []
    support_types = [
        str(row["support_type"]) for row in config["candidate_receptacle_types"]
    ]
    for raw in raw_scene_rows:
        scene_rows.append(
            {
                "scene": raw["scene"],
                "reset_success": raw["reset_success"],
                "reachable_query_success": raw["reachable_query_success"],
                "reachable_count": raw["reachable_count"],
                "pickupable_book_count": raw["pickupable_book_count"],
                "support_types": deepcopy(raw["support_types"]),
                "state_unchanged_after_spawn_queries": raw[
                    "state_unchanged_after_spawn_queries"
                ],
                "last_action_isolated_by_next_scene_reset": raw[
                    "last_action_isolated_by_next_scene_reset"
                ],
                "unexpected_action_count": raw["unexpected_action_count"],
            }
        )

    aggregates: list[dict[str, Any]] = []
    for support_type in support_types:
        rows = [
            next(
                row
                for row in scene["support_types"]
                if row["support_type"] == support_type
            )
            for scene in scene_rows
        ]
        aggregates.append(
            {
                "support_type": support_type,
                "metadata_count": sum(row["metadata_count"] for row in rows),
                "receptacle_true_count": sum(
                    row["receptacle_true_count"] for row in rows
                ),
                "receptacle_presence_scene_count": sum(
                    row["receptacle_true_count"] > 0 for row in rows
                ),
                "spawn_query_success_count": sum(
                    row["spawn_query_success_count"] for row in rows
                ),
                "positive_spawn_scene_count": sum(
                    row["positive_spawn_query_count"] > 0 for row in rows
                ),
                "spawn_coordinate_count": sum(
                    row["spawn_coordinate_count"] for row in rows
                ),
            }
        )
    passed = bool(
        not fatal_error_category
        and len(scene_rows) == len(config["inspected_scenes"])
        and all(row["reset_success"] for row in scene_rows)
        and all(row["reachable_query_success"] for row in scene_rows)
        and all(row["state_unchanged_after_spawn_queries"] for row in scene_rows)
        and all(row["unexpected_action_count"] == 0 for row in scene_rows)
    )
    summary = {
        "census_version": config["census_version"],
        "script_version": SCRIPT_VERSION,
        "claim": "read-only support-type census; not placement, qualification, or a memory comparison",
        "config_digest": stable_digest(config),
        "raw_digest": raw_digest,
        "inspected_scenes": list(config["inspected_scenes"]),
        "candidate_receptacle_types": support_types,
        "scene_count": len(scene_rows),
        "scenes": scene_rows,
        "aggregate_support_types": aggregates,
        "support_policy_candidate": build_policy_candidate(config, scene_rows),
        "passed": passed,
        "fatal_error_category": fatal_error_category,
        "coordinates_exposed": False,
        "placement_actions_run": False,
        "pickup_actions_run": False,
        "fallback_route_run": False,
        "memory_agents_run": False,
        "images_saved": False,
        **dict(git_state),
    }
    audit_public_summary(summary)
    return summary


def audit_public_summary(summary: Mapping[str, Any]) -> None:
    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            forbidden = PUBLIC_FORBIDDEN_KEYS.intersection(str(key) for key in value)
            if forbidden:
                raise ValueError(f"public census contains forbidden keys: {sorted(forbidden)}")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(summary)
    text = json.dumps(to_jsonable(summary), sort_keys=True)
    for forbidden in PUBLIC_FORBIDDEN_TEXT:
        if forbidden in text:
            raise ValueError(f"public census contains forbidden text: {forbidden}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "phase5_r1_support_census.json",
    )
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args(argv)

    config = load_census_config(args.config.resolve())
    git_state = _git_state()
    if git_state["working_tree_dirty"] is not False:
        raise RuntimeError("clean worktree required before the real support census")
    support_types = [
        str(row["support_type"]) for row in config["candidate_receptacle_types"]
    ]
    raw_scene_rows: list[dict[str, Any]] = []
    fatal_error_category = ""
    env = ThorEnv(controller_kwargs=CONTROLLER_SETTINGS)
    try:
        for scene in config["inspected_scenes"]:
            try:
                row = census_scene(env, scene=str(scene), support_types=support_types)
                raw_scene_rows.append(row)
                if row["state_unchanged_after_spawn_queries"] is not True:
                    fatal_error_category = "unexpected_state_mutation"
                    break
            except Exception as exc:
                fatal_error_category = type(exc).__name__
                break
    finally:
        env.close()

    raw = {
        "census_version": config["census_version"],
        "script_version": SCRIPT_VERSION,
        "boundary": "EVALUATOR-ONLY RAW CENSUS - NEVER PLANNER INPUT",
        "config_digest": stable_digest(config),
        "scenes": raw_scene_rows,
        "fatal_error_category": fatal_error_category,
        "placement_actions_run": False,
        "pickup_actions_run": False,
        "fallback_route_run": False,
        "memory_agents_run": False,
        "images_saved": False,
        **git_state,
    }
    raw_digest = stable_digest(raw)
    raw["raw_digest"] = raw_digest
    summary = build_public_summary(
        config=config,
        raw_scene_rows=raw_scene_rows,
        git_state=git_state,
        raw_digest=raw_digest,
        fatal_error_category=fatal_error_category,
    )
    _write_json(args.private_output.resolve(), raw)
    _write_json(args.public_output.resolve(), summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Evaluator-only repeated-reset start stability for ordered R2 tasks."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from embodied_memory_thor.phase5.anchors import stable_digest
from embodied_memory_thor.phase5.r2 import normalize_interactable_pose, pose_sort_key


STABILITY_POLICY_VERSION = "phase5-r2-start-visibility-stability-v2"
STABILITY_TRIALS_PER_POSE = 3
STABILITY_POSE_BUDGET = 256
STABILITY_OVERBOUND_SELECTION_POLICY = "deterministic-even-rank-v1"
REQUIRED_PRECONDITIONS = (
    "teleport_success",
    "cup_exists",
    "cup_pickupable",
    "cup_visible",
    "coffee_machine_exists",
    "coffee_machine_initially_off",
    "coffee_machine_initially_hidden",
)


class StabilityQueryError(RuntimeError):
    """The evaluator-only repeated pose query failed and cannot be skipped."""


def select_stability_pose_budget(
    poses: Sequence[Mapping[str, Any]],
    *,
    pose_budget: int = STABILITY_POSE_BUDGET,
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any], dict[str, Any]]:
    """Freeze an outcome-independent, rank-balanced pose subset when needed.

    The input is already in deterministic ``pose_sort_key`` order.  If it is
    over budget, systematic integer ranks span the complete ordered range,
    including both endpoints.  Selection happens before any stability trial
    and never reads visibility, route, interaction, or task outcomes.
    """

    if pose_budget <= 0:
        raise ValueError("stability pose budget must be positive")
    normalized = tuple(dict(pose) for pose in poses)
    observed_count = len(normalized)
    if observed_count <= pose_budget:
        selected_indexes = tuple(range(observed_count))
    elif pose_budget == 1:
        selected_indexes = (0,)
    else:
        selected_indexes = tuple(
            rank * (observed_count - 1) // (pose_budget - 1)
            for rank in range(pose_budget)
        )
        if len(set(selected_indexes)) != pose_budget:
            raise AssertionError("over-bound stability selection ranks are not unique")
    selected = tuple(normalized[index] for index in selected_indexes)
    selected_ranks = tuple(index + 1 for index in selected_indexes)
    digest_payload = {
        "policy": STABILITY_OVERBOUND_SELECTION_POLICY,
        "pose_budget": pose_budget,
        "observed_pose_count": observed_count,
        "selected_pose_ranks": selected_ranks,
    }
    public = {
        "selection_policy": STABILITY_OVERBOUND_SELECTION_POLICY,
        "pose_budget": pose_budget,
        "observed_pose_count": observed_count,
        "selected_pose_count": len(selected),
        "omitted_pose_count": observed_count - len(selected),
        "selection_applied": observed_count > pose_budget,
        "selection_before_trial_outcomes": True,
        "selection_digest": stable_digest(digest_payload),
    }
    private = {
        **public,
        "selected_pose_ranks": selected_ranks,
        "selected_pose_digests": tuple(stable_digest(pose) for pose in selected),
    }
    return selected, public, private


def _objects(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = metadata.get("objects", [])
    return [row for row in raw if isinstance(row, Mapping)] if isinstance(raw, list) else []


def _object(metadata: Mapping[str, Any], object_id: str) -> Mapping[str, Any] | None:
    return next(
        (row for row in _objects(metadata) if str(row.get("objectId", "")) == object_id),
        None,
    )


def _reset(env: Any, scene: str) -> Mapping[str, Any]:
    env.reset(scene)
    metadata = env.get_evaluator_state()
    return metadata if isinstance(metadata, Mapping) else {}


def sorted_targets(
    metadata: Mapping[str, Any], *, object_type: str, predicate: str
) -> list[Mapping[str, Any]]:
    return sorted(
        (
            row for row in _objects(metadata)
            if row.get("objectType") == object_type
            and row.get(predicate) is True
            and row.get("objectId")
        ),
        key=lambda row: str(row["objectId"]),
    )


def _standing_poses(raw: Any) -> tuple[dict[str, Any], ...]:
    rows = raw if isinstance(raw, list) else []
    poses = (
        pose for pose in (
            normalize_interactable_pose(row)
            for row in rows if isinstance(row, Mapping)
        )
        if pose is not None and pose["standing"] is True
    )
    return tuple(sorted(poses, key=pose_sort_key))


def select_first_standing_cup(
    env: Any, *, scene: str
) -> tuple[str | None, tuple[dict[str, Any], ...], list[dict[str, Any]]]:
    """Use sorted evaluator identity only to select the first standing Cup."""

    cups = sorted_targets(
        _reset(env, scene), object_type="Cup", predicate="pickupable"
    )
    audit: list[dict[str, Any]] = []
    for cup_order, cup in enumerate(cups, start=1):
        object_id = str(cup["objectId"])
        _reset(env, scene)
        event = env.step({"action": "GetInteractablePoses", "objectId": object_id})
        success = event.metadata.get("lastActionSuccess") is True
        row: dict[str, Any] = {
            "cup_order": cup_order,
            "object_id": object_id,
            "fresh_reset_before_query": True,
            "query_success": success,
            "query_error": str(event.metadata.get("errorMessage", "")),
            "standing_pose_count": 0,
            "selected": False,
        }
        if not success:
            audit.append(row)
            raise StabilityQueryError(
                f"selected-Cup pose query failed at Cup order {cup_order}"
            )
        poses = _standing_poses(event.metadata.get("actionReturn"))
        row["standing_pose_count"] = len(poses)
        row["selected"] = bool(poses)
        audit.append(row)
        if poses:
            return object_id, poses, audit
    return None, (), audit


def first_coffee_machine_id(env: Any, *, scene: str) -> str:
    machines = sorted_targets(
        _reset(env, scene), object_type="CoffeeMachine", predicate="toggleable"
    )
    if not machines:
        raise StabilityQueryError("no toggleable CoffeeMachine exists after reset")
    return str(machines[0]["objectId"])


def evaluate_preconditions(
    metadata: Mapping[str, Any], *, cup_id: str, machine_id: str
) -> dict[str, bool]:
    cup = _object(metadata, cup_id)
    machine = _object(metadata, machine_id)
    result = {
        "teleport_success": metadata.get("lastActionSuccess") is True,
        "cup_exists": cup is not None,
        "cup_pickupable": bool(cup and cup.get("pickupable") is True),
        "cup_visible": bool(cup and cup.get("visible") is True),
        "coffee_machine_exists": machine is not None,
        "coffee_machine_initially_off": bool(
            machine and machine.get("isToggled") is not True
        ),
        "coffee_machine_initially_hidden": bool(
            machine and machine.get("visible") is not True
        ),
    }
    if tuple(result) != REQUIRED_PRECONDITIONS:
        raise AssertionError("R2 stability precondition schema changed")
    return result


def audit_start_pose_stability(
    env: Any,
    *,
    scene: str,
    cup_id: str,
    machine_id: str,
    poses: Sequence[Mapping[str, Any]],
    trials_per_pose: int = STABILITY_TRIALS_PER_POSE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep only poses satisfying all seven conditions on every fresh reset."""

    if trials_per_pose != STABILITY_TRIALS_PER_POSE:
        raise ValueError("R2 stability policy requires exactly three trials per pose")
    stable: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for pose_order, raw_pose in enumerate(poses, start=1):
        reference = dict(raw_pose)
        pose_digest = stable_digest(reference)
        trials: list[dict[str, Any]] = []
        for trial_order in range(1, trials_per_pose + 1):
            _reset(env, scene)
            query = env.step(
                {"action": "GetInteractablePoses", "objectId": cup_id}
            )
            if query.metadata.get("lastActionSuccess") is not True:
                raise StabilityQueryError(
                    f"selected-Cup repeated pose query failed at pose {pose_order}, "
                    f"trial {trial_order}"
                )
            current_poses = _standing_poses(query.metadata.get("actionReturn"))
            current = next(
                (pose for pose in current_poses if stable_digest(pose) == pose_digest),
                None,
            )
            if current is None:
                trials.append({
                    "trial_order": trial_order,
                    "fresh_reset_before_query": True,
                    "query_success": True,
                    "pose_present_in_current_query": False,
                    "teleport_run": False,
                    "preconditions": {key: False for key in REQUIRED_PRECONDITIONS},
                    "passed": False,
                })
                continue
            event = env.step({"action": "TeleportFull", **current})
            preconditions = evaluate_preconditions(
                event.metadata, cup_id=cup_id, machine_id=machine_id
            )
            trials.append({
                "trial_order": trial_order,
                "fresh_reset_before_query": True,
                "query_success": True,
                "pose_present_in_current_query": True,
                "teleport_run": True,
                "pose": dict(current),
                "preconditions": preconditions,
                "passed": all(preconditions.values()),
            })
        success_count = sum(1 for row in trials if row["passed"])
        classification = (
            "stable" if success_count == trials_per_pose
            else "ineligible" if success_count == 0
            else "visibility_unstable"
        )
        row = {
            "pose_order": pose_order,
            "pose": reference,
            "pose_digest": pose_digest,
            "trials_required": trials_per_pose,
            "successful_trial_count": success_count,
            "classification": classification,
            "stable": classification == "stable",
            "trials": trials,
        }
        audit.append(row)
        if row["stable"]:
            stable.append(reference)
    return stable, audit


def reset_restoration(
    env: Any,
    *,
    scene: str,
    cup_id: str | None,
    machine_id: str | None,
) -> dict[str, Any]:
    """Reset and audit every identity that was known before success or error."""

    metadata = _reset(env, scene)
    cup = _object(metadata, cup_id) if cup_id is not None else None
    machine = _object(metadata, machine_id) if machine_id is not None else None
    inventory = metadata.get("inventoryObjects", [])
    result = {
        "scene_reset_observed": bool(metadata),
        "inventory_empty": isinstance(inventory, list) and not inventory,
    }
    if cup_id is not None:
        result.update({
            "cup_exists": cup is not None,
            "cup_pickupable": bool(cup and cup.get("pickupable") is True),
        })
    if machine_id is not None:
        result.update({
            "coffee_machine_exists": machine is not None,
            "coffee_machine_off": bool(
                machine and machine.get("isToggled") is not True
            ),
        })
    return {"passed": all(result.values()), **result}


def attempt_reset_restoration(
    env: Any,
    *,
    scene: str,
    cup_id: str | None,
    machine_id: str | None,
) -> dict[str, Any]:
    """Never bypass a restoration report when an evaluator query raises."""

    try:
        return reset_restoration(
            env,
            scene=scene,
            cup_id=cup_id,
            machine_id=machine_id,
        )
    except Exception as exc:
        return {
            "passed": False,
            "restoration_attempted": True,
            "restoration_error": f"{type(exc).__name__}: {exc}",
        }

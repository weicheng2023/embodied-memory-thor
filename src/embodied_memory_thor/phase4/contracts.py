"""Planner-safe Phase 4 contracts and hidden-state audits."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from embodied_memory_thor.env.object_parser import metadata_from_event, parse_objects
from embodied_memory_thor.utils.serialization import to_jsonable


TRACE_SCHEMA_VERSION = "phase4-trace-v1"
RGB_BOUNDARY_LABEL = (
    "Agent camera frame — human-visible artifact; "
    "not consumed by the metadata planner"
)
EVALUATOR_ONLY_LABEL = "EVALUATOR ONLY — NOT PLANNER INPUT"
EVALUATOR_CANARY = "__EVALUATOR_ONLY_CANARY__"

_AGENT_FIELDS = ("position", "rotation", "cameraHorizon", "isStanding")
_INVENTORY_FIELDS = ("objectId", "objectType")
_FORBIDDEN_KEYS = {
    "all_objects",
    "complete_metadata",
    "evaluator_debug",
    "evaluator_state",
    "full_metadata",
    "hidden_objects",
    "reachable_positions",
    "scene_objects",
    "unmet_goal_conditions",
}


def _safe_agent(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    return {
        key: deepcopy(raw.get(key))
        for key in _AGENT_FIELDS
        if key in raw
    }


def _safe_inventory(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    safe: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        safe.append(
            {
                key: deepcopy(item.get(key))
                for key in _INVENTORY_FIELDS
                if key in item
            }
        )
    return safe


def build_planner_observation(observation: Any) -> dict[str, Any]:
    """Whitelist current agent data and objects explicitly marked visible."""

    metadata = metadata_from_event(observation)
    objects = parse_objects(metadata, visible_only=True)
    return {
        "scene_name": str(metadata.get("sceneName", "")),
        "agent": _safe_agent(metadata.get("agent", {})),
        "objects": objects,
        "inventory": _safe_inventory(metadata.get("inventoryObjects", [])),
        "last_action": str(metadata.get("lastAction", "")),
        "last_action_success": bool(metadata.get("lastActionSuccess", True)),
        "last_action_error": str(metadata.get("errorMessage", "") or ""),
    }


def visible_object_ids(observation: Mapping[str, Any]) -> tuple[str, ...]:
    """Return stable object IDs from a planner-safe observation."""

    objects = observation.get("objects", [])
    if not isinstance(objects, list):
        return ()
    return tuple(
        sorted(
            str(obj.get("objectId"))
            for obj in objects
            if isinstance(obj, Mapping) and obj.get("visible") and obj.get("objectId")
        )
    )


def stable_digest(value: Any) -> str:
    """Hash the canonical JSON representation used for planner-input audits."""

    payload = json.dumps(
        to_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class PlannerRequest:
    """The complete and only information supplied to a Phase 4 planner."""

    task_name: str
    instruction: str
    task_stage: str
    step: int
    max_steps: int
    observation: dict[str, Any]
    allowed_actions: tuple[str, ...]
    retrieved_memory: tuple[dict[str, Any], ...] = ()
    recent_action_results: tuple[dict[str, Any], ...] = ()
    schema_version: str = TRACE_SCHEMA_VERSION
    rgb_consumed_by_planner: bool = False

    def snapshot(self, *, include_digest: bool = True) -> dict[str, Any]:
        payload = to_jsonable(asdict(self))
        if include_digest:
            payload["input_digest"] = stable_digest(payload)
        return payload

    @property
    def input_digest(self) -> str:
        return stable_digest(self.snapshot(include_digest=False))


@dataclass(frozen=True)
class PlannerDecision:
    """One structured planner output before environment execution."""

    action: dict[str, Any]
    target_object_type: str | None
    memory_guided: bool
    memory_record_ids: tuple[str, ...]
    reason_code: str
    rationale: str
    planner_name: str
    raw_response_id: str | None = None

    def snapshot(self) -> dict[str, Any]:
        return to_jsonable(asdict(self))


@dataclass(frozen=True)
class PlannerInputAudit:
    """Result of checking the exact serialized planner request."""

    passed: bool
    violations: tuple[str, ...] = field(default_factory=tuple)
    visible_object_ids: tuple[str, ...] = field(default_factory=tuple)
    memory_record_ids: tuple[str, ...] = field(default_factory=tuple)
    input_digest: str = ""

    def snapshot(self) -> dict[str, Any]:
        return to_jsonable(asdict(self))


def _walk_forbidden(value: Any, path: str, violations: list[str]) -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            child_path = f"{path}.{key}" if path else key
            if key.casefold() in _FORBIDDEN_KEYS:
                violations.append(f"forbidden_key:{child_path}")
            _walk_forbidden(item, child_path, violations)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _walk_forbidden(item, f"{path}[{index}]", violations)
        return
    if isinstance(value, str) and EVALUATOR_CANARY in value:
        violations.append(f"evaluator_canary:{path}")


def audit_planner_request(request: PlannerRequest) -> PlannerInputAudit:
    """Reject hidden objects, evaluator keys, or provenance-free memory."""

    payload = request.snapshot(include_digest=False)
    violations: list[str] = []
    _walk_forbidden(payload, "planner_request", violations)

    raw_objects = request.observation.get("objects", [])
    if not isinstance(raw_objects, list):
        violations.append("observation.objects_not_list")
        raw_objects = []
    for index, obj in enumerate(raw_objects):
        if not isinstance(obj, Mapping):
            violations.append(f"observation.objects[{index}]_not_mapping")
        elif not bool(obj.get("visible", False)):
            violations.append(f"hidden_object_in_observation:{index}")

    record_ids: list[str] = []
    for index, record in enumerate(request.retrieved_memory):
        record_id = str(record.get("record_id", ""))
        if not record_id:
            violations.append(f"memory_record_missing_id:{index}")
        else:
            record_ids.append(record_id)
        if not str(record.get("source_observation_id", "")):
            violations.append(f"memory_record_missing_provenance:{index}")
        if record.get("observed_visible") is not True:
            violations.append(f"memory_record_not_visible_derived:{index}")

    return PlannerInputAudit(
        passed=not violations,
        violations=tuple(violations),
        visible_object_ids=visible_object_ids(request.observation),
        memory_record_ids=tuple(record_ids),
        input_digest=request.input_digest,
    )


def memory_snapshot_diff(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Any]:
    """Return a compact record-level memory update for the step trace."""

    before_records = before.get("records", {})
    after_records = after.get("records", {})
    if not isinstance(before_records, Mapping):
        before_records = {}
    if not isinstance(after_records, Mapping):
        after_records = {}
    before_ids = set(map(str, before_records))
    after_ids = set(map(str, after_records))
    changed = sorted(
        record_id
        for record_id in before_ids & after_ids
        if before_records[record_id] != after_records[record_id]
    )
    return {
        "added_record_ids": sorted(after_ids - before_ids),
        "changed_record_ids": changed,
        "removed_record_ids": sorted(before_ids - after_ids),
    }

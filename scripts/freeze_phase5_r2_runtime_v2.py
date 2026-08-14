#!/usr/bin/env python3
"""Freeze six qualified R2 configurations into matched public/private v2 sets."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase5.anchors import stable_digest  # noqa: E402
from embodied_memory_thor.phase5.frozen_r2 import PRIVATE_BOUNDARY  # noqa: E402
from embodied_memory_thor.phase5.search import FrozenSearchRoute  # noqa: E402
from embodied_memory_thor.utils.serialization import to_jsonable  # noqa: E402


FREEZE_VERSION = "phase5-r2-runtime-freeze-v2"
RUNTIME_SET_VERSION = "phase5-r2-frozen-runtime-set-v2"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "phase5_r2_runtime_freeze_v2.json"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _one(rows: Any, configuration_id: str, *, label: str) -> Mapping[str, Any]:
    matches = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("configuration_id") == configuration_id
    ] if isinstance(rows, list) else []
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {label}: {configuration_id}")
    return matches[0]


def _validate_route(raw: Mapping[str, Any]) -> None:
    FrozenSearchRoute(
        route_id=str(raw.get("route_id", "")),
        task=str(raw.get("task", "")),
        scene=str(raw.get("scene", "")),
        source_qualification_route_digest=str(
            raw.get("source_qualification_route_digest", "")
        ),
        action_sequence_digest=str(raw.get("action_sequence_digest", "")),
        action_codes=str(raw.get("action_codes", "")),
        route_role=str(raw.get("route_role", "target_independent_fallback")),
        qualification_goal_input_used=bool(
            raw.get("qualification_goal_input_used", False)
        ),
        target_or_anchor_input_used=bool(raw.get("target_or_anchor_input_used", True)),
        schema_version=str(raw.get("schema_version", "")),
        entry_position_tolerance_meters=float(
            raw.get("entry_position_tolerance_meters", 0.05)
        ),
        entry_angle_tolerance_degrees=float(
            raw.get("entry_angle_tolerance_degrees", 1.0)
        ),
    ).validate()


def validate_freeze_config(config: Mapping[str, Any]) -> None:
    if config.get("freeze_version") != FREEZE_VERSION:
        raise ValueError("runtime freeze version mismatch")
    if config.get("runtime_set_version") != RUNTIME_SET_VERSION:
        raise ValueError("runtime-set version mismatch")
    rows = config.get("configurations")
    order = config.get("configuration_order")
    if not isinstance(rows, list) or not isinstance(order, list) or len(rows) != 6:
        raise ValueError("runtime freeze requires exactly six configurations")
    if [row.get("configuration_id") for row in rows if isinstance(row, Mapping)] != order:
        raise ValueError("runtime freeze configuration order mismatch")
    if config.get("planner_visible") is not False:
        raise ValueError("runtime freeze cannot be planner-visible")
    if config.get("memory_variants_run") is not False:
        raise ValueError("runtime freeze cannot run memory variants")
    if config.get("formal_use_allowed") is not False:
        raise ValueError("runtime freeze is not a formal result")
    for relative, expected in config.get("historical_artifacts_frozen", {}).items():
        if _sha256(PROJECT_ROOT / str(relative)) != str(expected):
            raise ValueError(f"historical artifact changed: {relative}")


def _public_material(
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    legacy_routes = {
        row["route_id"]: row
        for row in _read(PROJECT_ROOT / "configs" / "phase5_search_routes.json")["routes"]
    }
    public_rows: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    for spec in config["configurations"]:
        configuration_id = str(spec["configuration_id"])
        evidence = _read(PROJECT_ROOT / str(spec["evidence"]))
        if evidence.get("passed") is not True or evidence.get("configuration_id") != configuration_id:
            raise ValueError(f"qualification evidence is not a pass: {configuration_id}")
        public_path = spec.get("public_configuration")
        if public_path:
            public = _read(PROJECT_ROOT / str(public_path))
            subgoal = dict(public["subgoal_route"])
            fallback = dict(public["fallback_route"])
            source_digest = str(public["source_qualification_digest"])
            start_digest = str(public["start_pose_digest"])
            scene = str(public["scene"])
        else:
            subgoal = dict(legacy_routes[str(evidence["subgoal_route_id"])])
            fallback = dict(legacy_routes[str(evidence["fallback_route_id"])])
            source_digest = str(
                evidence.get("source_qualification_digest")
                or subgoal["source_qualification_route_digest"]
            )
            start_digest = str(evidence["start_pose_digest"])
            scene = str(evidence["scene"])
        for route in (subgoal, fallback):
            _validate_route(route)
            if route["source_qualification_route_digest"] != source_digest:
                raise ValueError(f"source route digest mismatch: {configuration_id}")
            routes.append(route)
        public_rows.append({
            "configuration_id": configuration_id,
            "scene": scene,
            "start_pose_digest": start_digest,
            "source_qualification_digest": source_digest,
            "subgoal_route_id": subgoal["route_id"],
            "subgoal_route_action_sequence_digest": subgoal["action_sequence_digest"],
            "fallback_route_id": fallback["route_id"],
            "fallback_route_action_sequence_digest": fallback["action_sequence_digest"],
            "public_evidence": str(spec["evidence"]),
        })
    if len({route["route_id"] for route in routes}) != 12:
        raise ValueError("runtime v2 requires 12 unique routes")
    return public_rows, routes


def build_private_registry(
    *,
    runtime_set_version: str,
    public_rows: list[Mapping[str, Any]],
    private_rows: list[Mapping[str, Any]],
    source_outputs: list[str],
) -> dict[str, Any]:
    configurations: list[dict[str, Any]] = []
    for public in public_rows:
        configuration_id = str(public["configuration_id"])
        source = _one(private_rows, configuration_id, label="private source")
        start_action = deepcopy(dict(source["start_action"]))
        pose = dict(start_action)
        pose.pop("action", None)
        if start_action.get("action") != "TeleportFull":
            raise ValueError(f"private start is not TeleportFull: {configuration_id}")
        if stable_digest(pose) != str(public["start_pose_digest"]):
            raise ValueError(f"private start-pose digest mismatch: {configuration_id}")
        configurations.append({
            "configuration_id": configuration_id,
            "scene": public["scene"],
            "target_cup_object_id": source["target_cup_object_id"],
            "coffee_machine_object_id": source["coffee_machine_object_id"],
            "start_action": start_action,
            "start_pose_digest": public["start_pose_digest"],
            "source_qualification_digest": public["source_qualification_digest"],
            "subgoal_route_id": public["subgoal_route_id"],
            "fallback_route_id": public["fallback_route_id"],
            "candidate_order": int(source.get("candidate_order", 1)),
        })
    private: dict[str, Any] = {
        "runtime_set_version": runtime_set_version,
        "boundary": PRIVATE_BOUNDARY,
        "planner_visible": False,
        "included_in_planner_metrics": False,
        "configuration_count": len(configurations),
        "source_qualification_outputs": source_outputs,
        "configurations": configurations,
    }
    private["private_configuration_set_digest"] = stable_digest(private)
    return private


def freeze(config_path: Path) -> dict[str, Any]:
    config = _read(config_path)
    validate_freeze_config(config)
    public_rows, routes = _public_material(config)
    private_rows: list[Mapping[str, Any]] = []
    source_outputs: list[str] = []
    loaded_sources: dict[str, dict[str, Any]] = {}
    for spec in config["configurations"]:
        relative = str(spec["private_source"])
        source_outputs.append(relative)
        source = loaded_sources.setdefault(relative, _read(PROJECT_ROOT / relative))
        if isinstance(source.get("configurations"), list):
            private_rows.extend(source["configurations"])
        else:
            private_rows.append(source)
    private = build_private_registry(
        runtime_set_version=RUNTIME_SET_VERSION,
        public_rows=public_rows,
        private_rows=private_rows,
        source_outputs=list(dict.fromkeys(source_outputs)),
    )
    private_digest = private["private_configuration_set_digest"]
    public = {
        "runtime_set_version": RUNTIME_SET_VERSION,
        "private_configuration_set_digest": private_digest,
        "configuration_count": 6,
        "configurations": public_rows,
        "planner_visible": False,
        "coordinates_public": False,
        "memory_agents_run": False,
        "formal_use_allowed": False,
        "claim_boundary": "six qualified R2 runtime contracts; no memory-agent comparison or formal result",
    }
    route_registry = {
        "schema_version": "phase5-search-route-v1",
        "runtime_set_version": RUNTIME_SET_VERSION,
        "routes": routes,
    }
    _write(PROJECT_ROOT / str(config["public_runtime_output"]), public)
    _write(PROJECT_ROOT / str(config["public_route_output"]), route_registry)
    _write(PROJECT_ROOT / str(config["private_runtime_output"]), private)
    return {
        "freeze_version": FREEZE_VERSION,
        "runtime_set_version": RUNTIME_SET_VERSION,
        "configuration_count": 6,
        "route_count": 12,
        "private_configuration_set_digest": private_digest,
        "planner_visible": False,
        "memory_variants_run": False,
        "formal_use_allowed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    try:
        result = freeze(args.config.expanduser().resolve())
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"phase5_r2_runtime_freeze_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

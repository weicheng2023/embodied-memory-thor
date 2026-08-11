"""Frozen target-independent search routes for matched Phase 5 variants."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SEARCH_ROUTE_SCHEMA_VERSION = "phase5-search-route-v1"
DEFAULT_SEARCH_ROUTES_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "phase5_search_routes.json"
)

_CODE_TO_ACTION = {
    "F": "MoveAhead",
    "L": "RotateLeft",
    "R": "RotateRight",
}


class SearchRouteError(ValueError):
    """Raised when a frozen route or its route-entry state is invalid."""


def _stable_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _agent_pose(observation: Mapping[str, Any]) -> dict[str, float]:
    agent = observation.get("agent", {})
    if not isinstance(agent, Mapping):
        raise SearchRouteError("planner-safe observation has no agent state")
    position = agent.get("position", {})
    rotation = agent.get("rotation", {})
    if not isinstance(position, Mapping) or not isinstance(rotation, Mapping):
        raise SearchRouteError("planner-safe observation has no agent pose")
    try:
        return {
            "x": float(position["x"]),
            "z": float(position["z"]),
            "yaw": float(rotation["y"]) % 360.0,
            "camera_horizon": float(agent.get("cameraHorizon", 0.0)),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise SearchRouteError("planner-safe agent pose is malformed") from exc


def _angle_delta(target: float, current: float) -> float:
    return (target - current + 180.0) % 360.0 - 180.0


@dataclass(frozen=True)
class FrozenSearchRoute:
    """Public action-only route qualified independently of target location."""

    route_id: str
    task: str
    scene: str
    source_qualification_route_digest: str
    action_sequence_digest: str
    action_codes: str
    target_or_anchor_input_used: bool = False
    schema_version: str = SEARCH_ROUTE_SCHEMA_VERSION
    entry_position_tolerance_meters: float = 0.05
    entry_angle_tolerance_degrees: float = 1.0

    def validate(self) -> None:
        if self.schema_version != SEARCH_ROUTE_SCHEMA_VERSION:
            raise SearchRouteError("unsupported search-route schema")
        if (
            not self.route_id.strip()
            or not self.task.strip()
            or not self.scene.strip()
        ):
            raise SearchRouteError("route_id, task, and scene must be non-empty")
        if self.target_or_anchor_input_used is not False:
            raise SearchRouteError("formal search route must be target independent")
        if not self.action_codes or any(
            code not in _CODE_TO_ACTION for code in self.action_codes
        ):
            raise SearchRouteError("route contains an unsupported action code")
        if self.entry_position_tolerance_meters <= 0:
            raise SearchRouteError("entry position tolerance must be positive")
        if self.entry_angle_tolerance_degrees <= 0:
            raise SearchRouteError("entry angle tolerance must be positive")
        if self.action_sequence_digest != _stable_digest(self.actions):
            raise SearchRouteError("route action-sequence digest mismatch")
        for value in (
            self.source_qualification_route_digest,
            self.action_sequence_digest,
        ):
            if len(value) != 64 or any(
                character not in "0123456789abcdef" for character in value
            ):
                raise SearchRouteError("route digests must be lowercase SHA-256 values")

    @property
    def actions(self) -> list[dict[str, str]]:
        return [{"action": _CODE_TO_ACTION[code]} for code in self.action_codes]

    @property
    def action_count(self) -> int:
        return len(self.action_codes)

    def public_reference(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "route_id": self.route_id,
            "task": self.task,
            "scene": self.scene,
            "source_qualification_route_digest": (
                self.source_qualification_route_digest
            ),
            "action_sequence_digest": self.action_sequence_digest,
            "action_count": self.action_count,
            "target_or_anchor_input_used": False,
        }


def load_frozen_search_route(
    route_id: str,
    *,
    path: str | Path = DEFAULT_SEARCH_ROUTES_PATH,
) -> FrozenSearchRoute:
    """Load one coordinate-free public route by opaque route ID."""

    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise SearchRouteError("search-route registry must be a mapping")
    if document.get("schema_version") != SEARCH_ROUTE_SCHEMA_VERSION:
        raise SearchRouteError("search-route registry schema mismatch")
    raw_routes = document.get("routes", [])
    if not isinstance(raw_routes, list):
        raise SearchRouteError("search-route registry routes must be a list")
    matches = [
        item
        for item in raw_routes
        if isinstance(item, Mapping) and item.get("route_id") == route_id
    ]
    if len(matches) != 1:
        raise SearchRouteError(f"expected exactly one frozen route {route_id!r}")
    raw = matches[0]
    route = FrozenSearchRoute(
        route_id=str(raw.get("route_id", "")),
        task=str(raw.get("task", "")),
        scene=str(raw.get("scene", "")),
        source_qualification_route_digest=str(
            raw.get("source_qualification_route_digest", "")
        ),
        action_sequence_digest=str(raw.get("action_sequence_digest", "")),
        action_codes=str(raw.get("action_codes", "")),
        target_or_anchor_input_used=raw.get(
            "target_or_anchor_input_used", True
        ),
        schema_version=str(
            raw.get("schema_version", document.get("schema_version", ""))
        ),
        entry_position_tolerance_meters=float(
            raw.get("entry_position_tolerance_meters", 0.05)
        ),
        entry_angle_tolerance_degrees=float(
            raw.get("entry_angle_tolerance_degrees", 1.0)
        ),
    )
    route.validate()
    return route


class FrozenSearchRouteState:
    """Align to observation-0 pose, then expose the frozen route one action at a time."""

    def __init__(
        self,
        route: FrozenSearchRoute,
        *,
        initial_observation: Mapping[str, Any],
    ) -> None:
        route.validate()
        self.route = route
        self._entry_pose = _agent_pose(initial_observation)
        self._coverage_cursor = 0
        self._alignment_action_count = 0

    @property
    def coverage_cursor(self) -> int:
        return self._coverage_cursor

    @property
    def alignment_action_count(self) -> int:
        return self._alignment_action_count

    def next_directive(self, observation: Mapping[str, Any]) -> dict[str, Any]:
        if self._coverage_cursor > 0:
            if self._coverage_cursor >= self.route.action_count:
                raise SearchRouteError("frozen search route exhausted")
            return self._directive(
                action=deepcopy(self.route.actions[self._coverage_cursor]),
                phase="coverage",
                action_index=self._coverage_cursor,
            )

        current = _agent_pose(observation)
        dx = current["x"] - self._entry_pose["x"]
        dz = current["z"] - self._entry_pose["z"]
        position_error = math.hypot(dx, dz)
        horizon_error = abs(
            current["camera_horizon"] - self._entry_pose["camera_horizon"]
        )
        yaw_error = _angle_delta(self._entry_pose["yaw"], current["yaw"])
        angle_tolerance = self.route.entry_angle_tolerance_degrees
        if position_error > self.route.entry_position_tolerance_meters:
            raise SearchRouteError("search route entry position mismatch")
        if horizon_error > angle_tolerance:
            raise SearchRouteError("search route entry camera-horizon mismatch")

        if abs(yaw_error) > angle_tolerance:
            if self._alignment_action_count >= 1:
                raise SearchRouteError("search route entry alignment did not converge")
            if abs(abs(yaw_error) - 90.0) > angle_tolerance:
                raise SearchRouteError("search route entry yaw mismatch")
            action_name = "RotateRight" if yaw_error > 0 else "RotateLeft"
            return self._directive(
                action={"action": action_name},
                phase="route_entry_alignment",
                action_index=None,
            )

        if self._coverage_cursor >= self.route.action_count:
            raise SearchRouteError("frozen search route exhausted")
        return self._directive(
            action=deepcopy(self.route.actions[self._coverage_cursor]),
            phase="coverage",
            action_index=self._coverage_cursor,
        )

    def record_result(
        self,
        directive: Mapping[str, Any],
        *,
        action: Mapping[str, Any],
        success: bool,
    ) -> None:
        expected = directive.get("action")
        if not isinstance(expected, Mapping) or dict(action) != dict(expected):
            raise SearchRouteError("planner action diverged from frozen search directive")
        if not success:
            raise SearchRouteError("frozen search directive failed")
        if directive.get("phase") == "route_entry_alignment":
            self._alignment_action_count += 1
            return
        if directive.get("phase") != "coverage":
            raise SearchRouteError("unknown frozen search phase")
        if directive.get("action_index") != self._coverage_cursor:
            raise SearchRouteError("frozen search cursor mismatch")
        self._coverage_cursor += 1

    def _directive(
        self,
        *,
        action: dict[str, str],
        phase: str,
        action_index: int | None,
    ) -> dict[str, Any]:
        return {
            "policy": "frozen_target_independent_route",
            "route_id": self.route.route_id,
            "action_sequence_digest": self.route.action_sequence_digest,
            "phase": phase,
            "action_index": action_index,
            "action": action,
        }

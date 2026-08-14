"""Load one qualified ordered-R2 configuration without exposing private state."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from embodied_memory_thor.env.base import EmbodiedEnv
from embodied_memory_thor.phase5.anchors import stable_digest
from embodied_memory_thor.phase5.search import FrozenSearchRoute, load_frozen_search_route


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PUBLIC_SET_PATH = PROJECT_ROOT / "configs" / "phase5_r2_frozen_runtime_v1.json"
DEFAULT_PRIVATE_SET_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "phase5_r2_frozen_runtime_v1"
    / "evaluator_only_configuration_registry.json"
)
PRIVATE_BOUNDARY = "EVALUATOR-ONLY FROZEN R2 CONFIGURATION - NEVER PLANNER INPUT"
R2_RUNTIME_SET_VERSION = "phase5-r2-frozen-runtime-set-v1"


class FrozenR2ConfigurationError(ValueError):
    """Raised when public and private frozen R2 artifacts do not match."""


def _metadata(env: EmbodiedEnv) -> Mapping[str, Any]:
    state = env.get_evaluator_state()
    return state if isinstance(state, Mapping) else {}


def _object(metadata: Mapping[str, Any], object_id: str) -> Mapping[str, Any] | None:
    objects = metadata.get("objects", [])
    if not isinstance(objects, list):
        return None
    return next(
        (
            obj
            for obj in objects
            if isinstance(obj, Mapping) and str(obj.get("objectId", "")) == object_id
        ),
        None,
    )


@dataclass(frozen=True)
class FrozenR2Configuration:
    """Private start material joined to an opaque public R2 contract."""

    configuration_id: str
    scene: str
    private_configuration_set_digest: str
    start_pose_digest: str
    source_qualification_digest: str
    subgoal_route_id: str
    fallback_route_id: str
    target_cup_object_id: str
    coffee_machine_object_id: str
    start_action: Mapping[str, Any]

    def public_reference(self) -> dict[str, Any]:
        return {
            "configuration_id": self.configuration_id,
            "scene": self.scene,
            "private_configuration_set_digest": (
                self.private_configuration_set_digest
            ),
            "start_pose_digest": self.start_pose_digest,
            "source_qualification_digest": self.source_qualification_digest,
            "subgoal_route_id": self.subgoal_route_id,
            "fallback_route_id": self.fallback_route_id,
            "planner_visible": False,
        }

    def apply(
        self,
        *,
        env: EmbodiedEnv,
        task_name: str,
        scene: str,
    ) -> Mapping[str, Any]:
        """Apply the frozen start and verify the ordered-task preconditions."""

        if task_name != "thor_cup_after_coffee_subgoal" or scene != self.scene:
            return {
                "boundary": PRIVATE_BOUNDARY,
                "configuration_id": self.configuration_id,
                "success": False,
                "private_error": "frozen R2 setup task/scene mismatch",
            }
        action = deepcopy(dict(self.start_action))
        try:
            env.step(action)
            metadata = _metadata(env)
        except Exception as exc:
            return {
                "boundary": PRIVATE_BOUNDARY,
                "configuration_id": self.configuration_id,
                "native_action": action,
                "success": False,
                "private_error": f"{type(exc).__name__}: {exc}",
            }

        native_success = bool(metadata.get("lastActionSuccess", False))
        native_error = str(metadata.get("errorMessage", "") or "")
        cup = _object(metadata, self.target_cup_object_id)
        machine = _object(metadata, self.coffee_machine_object_id)
        cup_visible = bool(cup and cup.get("visible") is True)
        cup_pickupable = bool(cup and cup.get("pickupable") is True)
        machine_toggleable = bool(machine and machine.get("toggleable") is True)
        machine_initially_hidden = bool(machine and machine.get("visible") is not True)
        machine_initially_off = bool(machine and machine.get("isToggled") is not True)
        success = bool(
            native_success
            and cup_visible
            and cup_pickupable
            and machine_toggleable
            and machine_initially_hidden
            and machine_initially_off
        )
        return {
            "boundary": PRIVATE_BOUNDARY,
            "configuration_id": self.configuration_id,
            "native_action": action,
            "native_action_success": native_success,
            "native_error": native_error,
            "target_cup_object_id": self.target_cup_object_id,
            "coffee_machine_object_id": self.coffee_machine_object_id,
            "cup_exists": cup is not None,
            "cup_visible": cup_visible,
            "cup_pickupable": cup_pickupable,
            "coffee_machine_exists": machine is not None,
            "coffee_machine_toggleable": machine_toggleable,
            "coffee_machine_initially_hidden": machine_initially_hidden,
            "coffee_machine_initially_off": machine_initially_off,
            "success": success,
            "private_error": "" if success else "frozen ordered-R2 start precondition failed",
        }


@dataclass(frozen=True)
class FrozenR2Runtime:
    configuration: FrozenR2Configuration
    subgoal_route: FrozenSearchRoute
    fallback_route: FrozenSearchRoute


def _one_match(rows: Any, configuration_id: str, *, label: str) -> Mapping[str, Any]:
    matches = [
        row
        for row in rows if isinstance(row, Mapping)
        and str(row.get("configuration_id", "")) == configuration_id
    ] if isinstance(rows, list) else []
    if len(matches) != 1:
        raise FrozenR2ConfigurationError(
            f"expected exactly one {label} R2 configuration"
        )
    return matches[0]


def load_frozen_r2_runtime(
    configuration_id: str,
    *,
    public_set_path: str | Path = DEFAULT_PUBLIC_SET_PATH,
    private_set_path: str | Path = DEFAULT_PRIVATE_SET_PATH,
    search_routes_path: str | Path | None = None,
    expected_runtime_set_version: str = R2_RUNTIME_SET_VERSION,
) -> FrozenR2Runtime:
    """Join public action-only routes to local evaluator-only start material."""

    public = json.loads(Path(public_set_path).read_text(encoding="utf-8"))
    private = json.loads(Path(private_set_path).read_text(encoding="utf-8"))
    if public.get("runtime_set_version") != expected_runtime_set_version:
        raise FrozenR2ConfigurationError("public frozen R2 runtime-set version mismatch")
    if private.get("runtime_set_version") != expected_runtime_set_version:
        raise FrozenR2ConfigurationError("private frozen R2 runtime-set version mismatch")

    expected_digest = str(public.get("private_configuration_set_digest", ""))
    actual_digest = str(private.get("private_configuration_set_digest", ""))
    digest_payload = deepcopy(private)
    digest_payload.pop("private_configuration_set_digest", None)
    if (
        len(expected_digest) != 64
        or actual_digest != expected_digest
        or stable_digest(digest_payload) != actual_digest
    ):
        raise FrozenR2ConfigurationError("private frozen R2 runtime-set digest mismatch")
    if (
        private.get("boundary") != PRIVATE_BOUNDARY
        or private.get("planner_visible") is not False
        or private.get("included_in_planner_metrics") is not False
    ):
        raise FrozenR2ConfigurationError("private frozen R2 set has an invalid boundary")

    public_row = _one_match(public.get("configurations"), configuration_id, label="public")
    private_row = _one_match(
        private.get("configurations"), configuration_id, label="private"
    )
    for key in ("scene", "start_pose_digest", "source_qualification_digest"):
        if str(public_row.get(key, "")) != str(private_row.get(key, "")):
            raise FrozenR2ConfigurationError(f"frozen R2 {key} mismatch")

    start_action = private_row.get("start_action", {})
    if not isinstance(start_action, Mapping) or start_action.get("action") != "TeleportFull":
        raise FrozenR2ConfigurationError("frozen R2 start action must be TeleportFull")
    pose = dict(start_action)
    pose.pop("action", None)
    start_pose_digest = str(public_row.get("start_pose_digest", ""))
    if stable_digest(pose) != start_pose_digest:
        raise FrozenR2ConfigurationError("frozen R2 start-pose digest mismatch")

    def load_route(key: str) -> FrozenSearchRoute:
        route_id = str(public_row.get(key, ""))
        return (
            load_frozen_search_route(route_id)
            if search_routes_path is None
            else load_frozen_search_route(route_id, path=search_routes_path)
        )

    subgoal_route = load_route("subgoal_route_id")
    fallback_route = load_route("fallback_route_id")
    source_digest = str(public_row.get("source_qualification_digest", ""))
    if (
        subgoal_route.scene != str(public_row.get("scene", ""))
        or fallback_route.scene != str(public_row.get("scene", ""))
        or subgoal_route.source_qualification_route_digest != source_digest
        or fallback_route.source_qualification_route_digest != source_digest
        or subgoal_route.route_role != "task_subgoal_navigation"
        or fallback_route.route_role != "target_independent_fallback"
        or subgoal_route.action_sequence_digest
        != str(public_row.get("subgoal_route_action_sequence_digest", ""))
        or fallback_route.action_sequence_digest
        != str(public_row.get("fallback_route_action_sequence_digest", ""))
    ):
        raise FrozenR2ConfigurationError("frozen R2 route contract mismatch")

    configuration = FrozenR2Configuration(
        configuration_id=configuration_id,
        scene=str(private_row.get("scene", "")),
        private_configuration_set_digest=actual_digest,
        start_pose_digest=start_pose_digest,
        source_qualification_digest=source_digest,
        subgoal_route_id=subgoal_route.route_id,
        fallback_route_id=fallback_route.route_id,
        target_cup_object_id=str(private_row.get("target_cup_object_id", "")),
        coffee_machine_object_id=str(private_row.get("coffee_machine_object_id", "")),
        start_action=deepcopy(dict(start_action)),
    )
    if not configuration.target_cup_object_id or not configuration.coffee_machine_object_id:
        raise FrozenR2ConfigurationError("frozen R2 object ID is empty")
    return FrozenR2Runtime(
        configuration=configuration,
        subgoal_route=subgoal_route,
        fallback_route=fallback_route,
    )

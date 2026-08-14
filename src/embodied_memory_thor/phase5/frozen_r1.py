"""Load and execute frozen evaluator-only R1 configurations safely."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from embodied_memory_thor.env.base import EmbodiedEnv
from embodied_memory_thor.phase5.anchors import stable_digest
from embodied_memory_thor.phase5.search import FrozenSearchRoute, load_frozen_search_route


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PUBLIC_SET_PATH = PROJECT_ROOT / "configs" / "phase5_r1_frozen_anchor_set_v1.json"
DEFAULT_PRIVATE_SET_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "phase5_r1_frozen_anchor_set_v1"
    / "evaluator_only_anchor_registry.json"
)
PRIVATE_BOUNDARY = "EVALUATOR-ONLY FROZEN R1 CONFIGURATION - NEVER PLANNER INPUT"


class FrozenR1ConfigurationError(ValueError):
    """Raised when public and private frozen R1 artifacts do not match."""


def _metadata(env: EmbodiedEnv) -> Mapping[str, Any]:
    state = env.get_evaluator_state()
    return state if isinstance(state, Mapping) else {}


def _action_result(metadata: Mapping[str, Any]) -> tuple[bool, str]:
    return (
        bool(metadata.get("lastActionSuccess", False)),
        str(metadata.get("errorMessage", "") or ""),
    )


def _target(
    metadata: Mapping[str, Any], object_id: str
) -> Mapping[str, Any] | None:
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


def _finite_point(raw: Any) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        raise FrozenR1ConfigurationError("frozen anchor point must be a mapping")
    point: dict[str, float] = {}
    for key in ("x", "y", "z"):
        try:
            value = float(raw[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise FrozenR1ConfigurationError(
                f"frozen anchor point has invalid {key}"
            ) from exc
        if not math.isfinite(value):
            raise FrozenR1ConfigurationError(
                f"frozen anchor point has non-finite {key}"
            )
        point[key] = value
    return point


@dataclass(frozen=True)
class FrozenR1Configuration:
    """Private runtime material joined to one coordinate-free public contract."""

    configuration_id: str
    scene: str
    anchor_id: str
    private_anchor_set_digest: str
    search_route_id: str
    start_pose_digest: str
    target_object_id: str
    start_action: Mapping[str, Any]
    target_point: Mapping[str, float]

    def public_reference(self) -> dict[str, Any]:
        return {
            "configuration_id": self.configuration_id,
            "scene": self.scene,
            "anchor_id": self.anchor_id,
            "private_anchor_set_digest": self.private_anchor_set_digest,
            "search_route_id": self.search_route_id,
            "start_pose_digest": self.start_pose_digest,
            "planner_visible": False,
        }

    def apply(
        self,
        *,
        env: EmbodiedEnv,
        task_name: str,
        scene: str,
    ) -> Mapping[str, Any]:
        """Apply the frozen start and verify the exact Book is initially visible."""

        if task_name != "thor_book_reacquire_k2" or scene != self.scene:
            return {
                "boundary": PRIVATE_BOUNDARY,
                "configuration_id": self.configuration_id,
                "success": False,
                "private_error": "frozen R1 setup task/scene mismatch",
            }
        action = deepcopy(dict(self.start_action))
        try:
            env.step(action)
            metadata = _metadata(env)
            native_success, error = _action_result(metadata)
        except Exception as exc:
            return {
                "boundary": PRIVATE_BOUNDARY,
                "configuration_id": self.configuration_id,
                "native_action": action,
                "success": False,
                "private_error": f"{type(exc).__name__}: {exc}",
            }
        target = _target(metadata, self.target_object_id)
        target_visible = bool(target and target.get("visible") is True)
        target_pickupable = bool(target and target.get("pickupable") is True)
        success = native_success and target_visible and target_pickupable
        return {
            "boundary": PRIVATE_BOUNDARY,
            "configuration_id": self.configuration_id,
            "native_action": action,
            "native_action_success": native_success,
            "native_error": error,
            "target_object_id": self.target_object_id,
            "target_exists": target is not None,
            "target_visible": target_visible,
            "target_pickupable": target_pickupable,
            "success": success,
            "private_error": "" if success else "frozen visible-start precondition failed",
        }


class FrozenBookRelocation:
    """Apply exactly one frozen native Book relocation after distraction three."""

    def __init__(self, configuration: FrozenR1Configuration) -> None:
        self.configuration = configuration
        self.intervention_id = f"{configuration.anchor_id}:relocation-v1"
        self.applied = False

    def maybe_apply(
        self,
        *,
        env: EmbodiedEnv,
        task_name: str,
        step: int,
        task_stage: str,
        agent_action: Mapping[str, Any],
        agent_action_success: bool,
        pre_intervention_observation: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        if self.applied:
            return None
        supported_trigger = (
            (task_stage == "controlled_distraction_3" and step == 3)
            or (task_stage == "controlled_distraction_v2_4" and step == 4)
            or (task_stage == "controlled_distraction_v3_3" and step == 3)
        )
        if not (
            task_name == "thor_book_reacquire_k2"
            and supported_trigger
            and agent_action_success
            and (
                (
                    task_stage.endswith("_3")
                    and agent_action.get("action") in {"LookUp", "Pass"}
                )
                or (
                    task_stage.endswith("_4")
                    and agent_action.get("action") == "LookUp"
                )
            )
        ):
            return None
        self.applied = True
        visible_target = any(
            isinstance(obj, Mapping)
            and str(obj.get("objectId", "")) == self.configuration.target_object_id
            and obj.get("visible") is True
            for obj in pre_intervention_observation.get("objects", [])
        )
        action = {
            "action": "PlaceObjectAtPoint",
            "objectId": self.configuration.target_object_id,
            "position": deepcopy(dict(self.configuration.target_point)),
        }
        if visible_target:
            return self._record(
                step=step,
                trigger_stage=task_stage,
                action=action,
                success=False,
                error="Book remained visible at the frozen intervention milestone",
                target=None,
            )
        try:
            env.step(action)
            metadata = _metadata(env)
            native_success, error = _action_result(metadata)
            target = _target(metadata, self.configuration.target_object_id)
        except Exception as exc:
            return self._record(
                step=step,
                trigger_stage=task_stage,
                action=action,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                target=None,
            )
        success = bool(
            native_success
            and target is not None
            and target.get("visible") is not True
        )
        if not success and not error:
            error = "frozen relocation postcondition failed"
        return self._record(
            step=step,
            trigger_stage=task_stage,
            action=action,
            success=success,
            error=error,
            target=target,
        )

    def _record(
        self,
        *,
        step: int,
        trigger_stage: str,
        action: Mapping[str, Any],
        success: bool,
        error: str,
        target: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "boundary": PRIVATE_BOUNDARY,
            "intervention_id": self.intervention_id,
            "configuration_id": self.configuration.configuration_id,
            "anchor_id": self.configuration.anchor_id,
            "trigger_step": step,
            "trigger_stage": trigger_stage,
            "included_in_planner_metrics": False,
            "planner_visible": False,
            "native_action": deepcopy(dict(action)),
            "target_exists_after": target is not None,
            "target_visible_after": (
                bool(target.get("visible", False)) if target is not None else None
            ),
            "success": bool(success),
            "private_error": str(error),
        }


@dataclass(frozen=True)
class FrozenR1Runtime:
    configuration: FrozenR1Configuration
    search_route: FrozenSearchRoute

    def intervention(self) -> FrozenBookRelocation:
        return FrozenBookRelocation(self.configuration)


def load_frozen_r1_runtime(
    configuration_id: str,
    *,
    public_set_path: str | Path = DEFAULT_PUBLIC_SET_PATH,
    private_set_path: str | Path = DEFAULT_PRIVATE_SET_PATH,
    search_routes_path: str | Path | None = None,
) -> FrozenR1Runtime:
    """Join one public opaque contract to its local evaluator-only material."""

    public = json.loads(Path(public_set_path).read_text(encoding="utf-8"))
    private = json.loads(Path(private_set_path).read_text(encoding="utf-8"))
    expected_digest = str(public.get("private_anchor_set_digest", ""))
    actual_digest = str(private.get("private_anchor_set_digest", ""))
    digest_payload = deepcopy(private)
    digest_payload.pop("private_anchor_set_digest", None)
    if (
        len(expected_digest) != 64
        or actual_digest != expected_digest
        or stable_digest(digest_payload) != actual_digest
    ):
        raise FrozenR1ConfigurationError("private frozen anchor-set digest mismatch")
    if (
        private.get("planner_visible") is not False
        or private.get("included_in_planner_metrics") is not False
    ):
        raise FrozenR1ConfigurationError("private anchor set has an invalid boundary")

    public_rows = public.get("scenes", [])
    private_rows = private.get("anchors", [])
    public_matches = [
        row
        for row in public_rows
        if isinstance(row, Mapping)
        and str(row.get("configuration_id", "")) == configuration_id
    ]
    private_matches = [
        row
        for row in private_rows
        if isinstance(row, Mapping)
        and str(row.get("configuration_id", "")) == configuration_id
    ]
    if len(public_matches) != 1 or len(private_matches) != 1:
        raise FrozenR1ConfigurationError(
            "expected exactly one public and private R1 configuration"
        )
    public_row = public_matches[0]
    anchor = private_matches[0]
    for key in ("scene", "anchor_id"):
        if str(public_row.get(key, "")) != str(anchor.get(key, "")):
            raise FrozenR1ConfigurationError(f"frozen R1 {key} mismatch")

    evidence = anchor.get("qualification_evidence", {})
    trial = evidence.get("first_physical_trial", {}) if isinstance(evidence, Mapping) else {}
    setup_rows = trial.get("setup", []) if isinstance(trial, Mapping) else []
    if not isinstance(setup_rows, list) or len(setup_rows) != 1:
        raise FrozenR1ConfigurationError("frozen R1 start must contain one setup action")
    setup = setup_rows[0]
    start_action = setup.get("action", {}) if isinstance(setup, Mapping) else {}
    if not isinstance(start_action, Mapping) or start_action.get("action") != "TeleportFull":
        raise FrozenR1ConfigurationError("frozen R1 start action must be TeleportFull")
    pose = dict(start_action)
    pose.pop("action", None)
    start_pose_digest = str(public_row.get("start_pose_digest", ""))
    if stable_digest(pose) != start_pose_digest:
        raise FrozenR1ConfigurationError("frozen R1 start-pose digest mismatch")

    route_path = search_routes_path if search_routes_path is not None else None
    route = (
        load_frozen_search_route(str(public_row.get("search_route_id", "")))
        if route_path is None
        else load_frozen_search_route(
            str(public_row.get("search_route_id", "")), path=route_path
        )
    )
    if (
        route.scene != str(anchor.get("scene", ""))
        or route.source_qualification_route_digest
        != str(anchor.get("coverage_route_digest", ""))
    ):
        raise FrozenR1ConfigurationError("frozen R1 search-route mismatch")

    configuration = FrozenR1Configuration(
        configuration_id=configuration_id,
        scene=str(anchor["scene"]),
        anchor_id=str(anchor["anchor_id"]),
        private_anchor_set_digest=actual_digest,
        search_route_id=route.route_id,
        start_pose_digest=start_pose_digest,
        target_object_id=str(anchor.get("target_object_id", "")),
        start_action=deepcopy(dict(start_action)),
        target_point=_finite_point(anchor.get("target_point")),
    )
    if not configuration.target_object_id:
        raise FrozenR1ConfigurationError("frozen R1 target object ID is empty")
    return FrozenR1Runtime(configuration=configuration, search_route=route)

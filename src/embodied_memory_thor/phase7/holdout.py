"""Frozen generic-policy contracts for the Phase-7A R1 holdout."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from embodied_memory_thor.env.base import EmbodiedEnv
from embodied_memory_thor.phase5.anchors import (
    normalize_absolute_horizon_degrees,
    stable_digest,
)
from embodied_memory_thor.phase5.budgeted_fallback import (
    build_target_independent_budgeted_visual_fallback_route,
)
from embodied_memory_thor.phase5.search import (
    SEARCH_ROUTE_SCHEMA_VERSION,
    FrozenSearchRoute,
    load_frozen_search_route,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PHASE7A_VARIANTS = ("no_memory", "short_memory_k2", "object_memory")
PHASE7A_GENERIC_ROUTE_POLICY_VERSION = (
    "phase7a-generic-budgeted-visual-fallback-v1"
)
PHASE7A_ROUTE_ACTION_LIMIT = 1984
PHASE7A_ROUTE_BIN_SIZE_STEPS = 3
PHASE7A_TASK = "thor_book_reacquire_k2"
PHASE7A_CONDITION = "stable"
PHASE7A_PRIVATE_BOUNDARY = (
    "EVALUATOR-ONLY PHASE7A HOLDOUT SETUP - NEVER PLANNER INPUT"
)
PHASE7A_PRIVATE_REGISTRY_VERSION = "phase7a-holdout-evaluator-registry-v1"
PHASE7A_ROUTE_REGISTRY_VERSION = "phase7a-holdout-route-registry-v1"

DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "configs" / "phase7" / "holdout_manifest.json"
DEFAULT_PRIVATE_REGISTRY_PATH = (
    PROJECT_ROOT
    / "configs"
    / "phase7"
    / "evaluator_only"
    / "holdout_registry_v1.json"
)
DEFAULT_ROUTE_REGISTRY_PATH = (
    PROJECT_ROOT / "configs" / "phase7" / "holdout_routes_v1.json"
)

_ACTION_TO_CODE = {
    "LookDown": "D",
    "MoveAhead": "F",
    "RotateLeft": "L",
    "RotateRight": "R",
    "LookUp": "U",
}
_PUBLIC_FORBIDDEN_KEYS = {
    "anchor",
    "anchor_id",
    "candidate_outcome",
    "interactable_poses",
    "objectid",
    "reachable_positions",
    "start_action",
    "target_object_id",
    "target_point",
    "x",
    "y",
    "z",
}


class Phase7AHoldoutError(ValueError):
    """Raised when a Phase-7A contract or evaluator boundary is invalid."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _action_sequence_digest(actions: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(
        list(actions), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalize_interactable_pose(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """Normalize one evaluator-only AI2-THOR interactable pose."""

    try:
        rotation = raw.get("rotation", 0.0)
        if isinstance(rotation, Mapping):
            rotation = rotation.get("y", 0.0)
        pose = {
            "x": float(raw["x"]),
            "y": float(raw["y"]),
            "z": float(raw["z"]),
            "rotation": float(rotation) % 360.0,
            "horizon": normalize_absolute_horizon_degrees(
                float(raw.get("horizon", raw.get("cameraHorizon", 0.0)))
            ),
            "standing": bool(raw.get("standing", True)),
        }
    except (KeyError, TypeError, ValueError):
        return None
    if not all(
        math.isfinite(float(pose[key]))
        for key in ("x", "y", "z", "rotation", "horizon")
    ):
        return None
    return pose


def pose_sort_key(pose: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        float(pose["x"]),
        float(pose["z"]),
        float(pose["rotation"]),
        float(pose["horizon"]),
        not bool(pose["standing"]),
        float(pose["y"]),
    )


def distraction_actions_for_horizon(horizon: float) -> tuple[str, ...]:
    """Return the exact target-independent Phase-5 distraction-v4 template."""

    normalized = normalize_absolute_horizon_degrees(horizon)
    delta = -normalized
    alignment_action = "LookDown" if delta > 0 else "LookUp"
    alignment = (alignment_action,) * int(abs(delta) / 30.0)
    return ("RotateRight", "RotateRight", *alignment, "Pass")


def build_phase7a_generic_route(
    *,
    reachable_positions: Sequence[Mapping[str, Any]],
    start_pose: Mapping[str, Any],
    grid_size: float = 0.25,
    bin_size_steps: int = PHASE7A_ROUTE_BIN_SIZE_STEPS,
    action_limit: int = PHASE7A_ROUTE_ACTION_LIMIT,
) -> dict[str, Any]:
    """Build the frozen Phase-7A target-independent route successor."""

    route = build_target_independent_budgeted_visual_fallback_route(
        reachable_positions=reachable_positions,
        start_position={"x": start_pose["x"], "z": start_pose["z"]},
        start_yaw=float(start_pose["rotation"]),
        start_camera_horizon_degrees=float(start_pose["horizon"]),
        grid_size=grid_size,
        bin_size_steps=bin_size_steps,
        action_limit=action_limit,
    )
    route["source_algorithm_version"] = route["route_version"]
    route["route_version"] = PHASE7A_GENERIC_ROUTE_POLICY_VERSION
    route["phase7_successor_study"] = True
    route["route_digest"] = stable_digest(
        {key: value for key, value in route.items() if key != "route_digest"}
    )
    return route


def build_public_route_contract(
    *, scene: str, configuration_id: str, route: Mapping[str, Any]
) -> dict[str, Any]:
    """Convert a private construction record to an action-only public contract."""

    action_names: list[str] = []
    for row in route.get("actions", []):
        if not isinstance(row, Mapping) or not isinstance(row.get("action"), Mapping):
            raise Phase7AHoldoutError("generic route action row is malformed")
        action_names.append(str(row["action"].get("action", "")))
    try:
        action_codes = "".join(_ACTION_TO_CODE[name] for name in action_names)
    except KeyError as exc:
        raise Phase7AHoldoutError(
            f"generic route contains unsupported action: {exc.args[0]}"
        ) from exc
    actions = [{"action": name} for name in action_names]
    contract = {
        "schema_version": SEARCH_ROUTE_SCHEMA_VERSION,
        "route_id": f"{configuration_id}_generic_budgeted_v1",
        "task": PHASE7A_TASK,
        "scene": scene,
        "source_qualification_route_digest": str(route["route_digest"]),
        "action_sequence_digest": _action_sequence_digest(actions),
        "action_codes": action_codes,
        "route_role": "target_independent_fallback",
        "qualification_goal_input_used": False,
        "target_or_anchor_input_used": False,
        "entry_position_tolerance_meters": 0.05,
        "entry_angle_tolerance_degrees": 1.0,
    }
    FrozenSearchRoute(
        route_id=contract["route_id"],
        task=contract["task"],
        scene=contract["scene"],
        source_qualification_route_digest=contract[
            "source_qualification_route_digest"
        ],
        action_sequence_digest=contract["action_sequence_digest"],
        action_codes=contract["action_codes"],
        route_role=contract["route_role"],
        qualification_goal_input_used=False,
        target_or_anchor_input_used=False,
        entry_position_tolerance_meters=0.05,
        entry_angle_tolerance_degrees=1.0,
    ).validate()
    validate_public_artifact(contract)
    return contract


def validate_public_artifact(value: Any, *, path: str = "root") -> None:
    """Reject evaluator-only fields from a public Phase-7 artifact."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).replace("-", "_").lower()
            if normalized in _PUBLIC_FORBIDDEN_KEYS:
                raise Phase7AHoldoutError(
                    f"evaluator-only field in public artifact: {path}.{key}"
                )
            validate_public_artifact(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            validate_public_artifact(child, path=f"{path}[{index}]")


def _metadata(env: EmbodiedEnv) -> Mapping[str, Any]:
    state = env.get_evaluator_state()
    return state if isinstance(state, Mapping) else {}


def _target(metadata: Mapping[str, Any], object_id: str) -> Mapping[str, Any] | None:
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
class Phase7AHoldoutConfiguration:
    """Evaluator-only setup joined to a coordinate-free selected contract."""

    configuration_id: str
    scene: str
    target_object_id: str
    start_action: Mapping[str, Any]
    start_pose_digest: str
    private_registry_digest: str
    route_id: str

    def public_reference(self) -> dict[str, Any]:
        return {
            "configuration_id": self.configuration_id,
            "scene": self.scene,
            "start_pose_digest": self.start_pose_digest,
            "private_registry_digest": self.private_registry_digest,
            "route_id": self.route_id,
            "planner_visible": False,
        }

    def apply(
        self, *, env: EmbodiedEnv, task_name: str, scene: str
    ) -> Mapping[str, Any]:
        if task_name != PHASE7A_TASK or scene != self.scene:
            return {
                "boundary": PHASE7A_PRIVATE_BOUNDARY,
                "configuration_id": self.configuration_id,
                "success": False,
                "private_error": "Phase7A setup task/scene mismatch",
            }
        action = deepcopy(dict(self.start_action))
        try:
            env.step(action)
            metadata = _metadata(env)
            native_success = bool(metadata.get("lastActionSuccess", False))
            target = _target(metadata, self.target_object_id)
            target_visible = bool(target and target.get("visible") is True)
            target_pickupable = bool(target and target.get("pickupable") is True)
            success = native_success and target_visible and target_pickupable
            error = str(metadata.get("errorMessage", "") or "")
        except Exception as exc:
            return {
                "boundary": PHASE7A_PRIVATE_BOUNDARY,
                "configuration_id": self.configuration_id,
                "native_action": action,
                "success": False,
                "private_error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "boundary": PHASE7A_PRIVATE_BOUNDARY,
            "configuration_id": self.configuration_id,
            "native_action": action,
            "native_action_success": native_success,
            "native_error": error,
            "target_object_id": self.target_object_id,
            "target_exists": target is not None,
            "target_visible": target_visible,
            "target_pickupable": target_pickupable,
            "success": success,
            "private_error": "" if success else "Phase7A visible-start precondition failed",
        }


@dataclass(frozen=True)
class Phase7AHoldoutRuntime:
    configuration: Phase7AHoldoutConfiguration
    search_route: FrozenSearchRoute


def load_phase7a_holdout_runtime(
    configuration_id: str,
    *,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    private_registry_path: str | Path = DEFAULT_PRIVATE_REGISTRY_PATH,
    route_registry_path: str | Path = DEFAULT_ROUTE_REGISTRY_PATH,
) -> Phase7AHoldoutRuntime:
    """Load one matrix-frozen Phase-7A configuration without planner leakage."""

    manifest_file = Path(manifest_path)
    private_file = Path(private_registry_path)
    routes_file = Path(route_registry_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    private = json.loads(private_file.read_text(encoding="utf-8"))
    if manifest.get("status") != "matrix_frozen_no_outcomes":
        raise Phase7AHoldoutError("Phase7A selected matrix is not frozen")
    if _sha256(private_file) != manifest.get("evaluator_registry_sha256"):
        raise Phase7AHoldoutError("Phase7A evaluator registry file digest mismatch")
    if _sha256(routes_file) != manifest.get("route_registry_sha256"):
        raise Phase7AHoldoutError("Phase7A route registry file digest mismatch")
    if (
        private.get("registry_version") != PHASE7A_PRIVATE_REGISTRY_VERSION
        or private.get("boundary") != PHASE7A_PRIVATE_BOUNDARY
        or private.get("planner_visible") is not False
        or private.get("included_in_planner_metrics") is not False
    ):
        raise Phase7AHoldoutError("Phase7A evaluator registry boundary mismatch")
    expected_private_digest = str(manifest.get("private_registry_digest", ""))
    actual_private_digest = str(private.get("private_registry_digest", ""))
    digest_payload = deepcopy(private)
    digest_payload.pop("private_registry_digest", None)
    if (
        actual_private_digest != expected_private_digest
        or stable_digest(digest_payload) != actual_private_digest
    ):
        raise Phase7AHoldoutError("Phase7A evaluator registry content mismatch")

    public_rows = manifest.get("selected_configurations", [])
    private_rows = private.get("configurations", [])
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
        raise Phase7AHoldoutError("expected one public/private Phase7A configuration")
    public = public_matches[0]
    hidden = private_matches[0]
    for key in ("scene", "configuration_id", "start_pose_digest", "route_id"):
        if str(public.get(key, "")) != str(hidden.get(key, "")):
            raise Phase7AHoldoutError(f"Phase7A selected {key} mismatch")
    start_action = hidden.get("start_action")
    if not isinstance(start_action, Mapping) or start_action.get("action") != "TeleportFull":
        raise Phase7AHoldoutError("Phase7A start action must be TeleportFull")
    pose = dict(start_action)
    pose.pop("action", None)
    if stable_digest(pose) != str(public["start_pose_digest"]):
        raise Phase7AHoldoutError("Phase7A start pose digest mismatch")

    route = load_frozen_search_route(str(public["route_id"]), path=routes_file)
    if route.scene != str(public["scene"]):
        raise Phase7AHoldoutError("Phase7A route scene mismatch")
    configuration = Phase7AHoldoutConfiguration(
        configuration_id=configuration_id,
        scene=str(public["scene"]),
        target_object_id=str(hidden.get("target_object_id", "")),
        start_action=deepcopy(dict(start_action)),
        start_pose_digest=str(public["start_pose_digest"]),
        private_registry_digest=actual_private_digest,
        route_id=route.route_id,
    )
    if not configuration.target_object_id:
        raise Phase7AHoldoutError("Phase7A target object ID is empty")
    return Phase7AHoldoutRuntime(configuration=configuration, search_route=route)

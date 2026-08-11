"""Deterministic and OpenAI-compatible planners for Phase 4."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from embodied_memory_thor.actions import ActionSpace
from embodied_memory_thor.phase4.contracts import PlannerDecision, PlannerRequest


THOR_BOOK_ACTIONS = (
    "LookDown",
    "LookUp",
    "MoveAhead",
    "Pass",
    "PickupObject",
    "RotateLeft",
    "RotateRight",
)
THOR_CUP_COFFEE_ACTIONS = THOR_BOOK_ACTIONS + ("ToggleObjectOn",)


class StructuredPlanner(Protocol):
    """One-step structured planner contract."""

    name: str

    def plan(self, request: PlannerRequest) -> PlannerDecision: ...


class PlannerOutputError(RuntimeError):
    """Raised when an external planner cannot produce a safe action."""


def _visible_objects(request: PlannerRequest) -> list[Mapping[str, Any]]:
    raw = request.observation.get("objects", [])
    return [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []


def _agent_vector(observation: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    agent = observation.get("agent", {})
    if not isinstance(agent, Mapping):
        return {}
    value = agent.get(field, {})
    return value if isinstance(value, Mapping) else {}


def _number(mapping: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = mapping.get(key, default)
    return float(value) if isinstance(value, (int, float)) else default


def _angle_delta(target: float, current: float) -> float:
    return (target - current + 180.0) % 360.0 - 180.0


def _last_failed_move(request: PlannerRequest) -> bool:
    if not request.recent_action_results:
        return False
    last = request.recent_action_results[-1]
    action = last.get("action", {})
    return (
        isinstance(action, Mapping)
        and action.get("action") == "MoveAhead"
        and last.get("success") is False
    )


class ThorBookReacquirePlanner:
    """Deterministic metadata planner that reads only ``PlannerRequest``."""

    name = "thor_book_reacquire_deterministic"

    def __init__(
        self,
        *,
        position_tolerance: float = 0.18,
        interaction_distance: float = 1.5,
        rotation_tolerance_degrees: float = 1.0,
        visible_target_rotation_tolerance_degrees: float = 45.0,
        horizon_tolerance_degrees: float = 1.0,
    ) -> None:
        self.position_tolerance = position_tolerance
        self.interaction_distance = interaction_distance
        self.rotation_tolerance_degrees = rotation_tolerance_degrees
        self.visible_target_rotation_tolerance_degrees = (
            visible_target_rotation_tolerance_degrees
        )
        self.horizon_tolerance_degrees = horizon_tolerance_degrees

    def plan(self, request: PlannerRequest) -> PlannerDecision:
        stage = request.task_stage
        visible_book = next(
            (
                obj
                for obj in _visible_objects(request)
                if obj.get("visible") is True and obj.get("objectType") == "Book"
            ),
            None,
        )
        visible_cup = next(
            (
                obj
                for obj in _visible_objects(request)
                if obj.get("visible") is True and obj.get("objectType") == "Cup"
            ),
            None,
        )
        visible_coffee_machine = next(
            (
                obj
                for obj in _visible_objects(request)
                if obj.get("visible") is True
                and obj.get("objectType") == "CoffeeMachine"
            ),
            None,
        )

        if stage == "controlled_distraction":
            return self._decision(
                {"action": "RotateRight"},
                reason_code="controlled_distraction",
                rationale="Rotate away until the initially observed Book leaves view.",
            )

        phase5_distraction_actions = {
            "controlled_distraction_1": ("RotateRight", "rotate_away"),
            "controlled_distraction_2": ("LookDown", "change_camera_horizon"),
            "controlled_distraction_3": ("LookUp", "restore_camera_horizon"),
        }
        if stage in phase5_distraction_actions:
            action_name, reason_suffix = phase5_distraction_actions[stage]
            return self._decision(
                {"action": action_name},
                reason_code=f"controlled_distraction_{reason_suffix}",
                rationale=(
                    "Execute the frozen shared distraction sequence before "
                    "target reacquisition."
                ),
            )

        if stage == "toggle_coffee_machine":
            if visible_coffee_machine is not None:
                approach = self._approach_visible_target(
                    request, visible_coffee_machine, target_type="CoffeeMachine"
                )
                if approach is not None:
                    return approach
                return self._decision(
                    {
                        "action": "ToggleObjectOn",
                        "objectId": str(visible_coffee_machine["objectId"]),
                    },
                    target_object_type="CoffeeMachine",
                    reason_code="visible_ordered_subgoal_interaction",
                    rationale=(
                        "The ordered CoffeeMachine subgoal is currently visible "
                        "and must be completed before Cup pickup."
                    ),
                )
            return self._decision(
                {"action": "RotateRight"},
                target_object_type="CoffeeMachine",
                reason_code="systematic_subgoal_search",
                rationale=(
                    "Search clockwise for the CoffeeMachine using the shared "
                    "observation-only policy."
                ),
            )

        if stage == "pickup_cup" and visible_cup is not None:
            approach = self._approach_visible_target(
                request, visible_cup, target_type="Cup"
            )
            if approach is not None:
                return approach
            return self._decision(
                {"action": "PickupObject", "objectId": str(visible_cup["objectId"])},
                target_object_type="Cup",
                reason_code="visible_target_interaction",
                rationale=(
                    "The CoffeeMachine subgoal is complete and the reacquired Cup "
                    "is currently visible."
                ),
            )

        if stage == "reacquire_cup":
            if request.retrieved_memory:
                return self._memory_navigation(
                    request, request.retrieved_memory[0], target_type="Cup"
                )
            if request.shared_search is not None:
                return self._shared_search_decision(request, target_type="Cup")
            return self._decision(
                {"action": "RotateRight"},
                target_object_type="Cup",
                reason_code="systematic_search",
                rationale=(
                    "No Cup memory is available, so continue the shared clockwise scan."
                ),
            )

        if stage == "pickup_book" and visible_book is not None:
            approach = self._approach_visible_book(request, visible_book)
            if approach is not None:
                return approach
            return self._decision(
                {"action": "PickupObject", "objectId": str(visible_book["objectId"])},
                target_object_type="Book",
                reason_code="visible_target_interaction",
                rationale="The reacquired Book is currently visible and can be picked up.",
            )

        if stage == "reacquire_book":
            if request.retrieved_memory:
                record = request.retrieved_memory[0]
                return self._memory_navigation(request, record)
            if request.shared_search is not None:
                return self._shared_search_decision(request, target_type="Book")
            return self._decision(
                {"action": "RotateRight"},
                target_object_type="Book",
                reason_code="systematic_search",
                rationale="No Book memory is available, so continue a systematic rotation scan.",
            )

        return self._decision(
            {"action": "Pass"},
            reason_code=stage,
            rationale=f"No executable task action is defined for stage {stage!r}.",
        )

    def _shared_search_decision(
        self,
        request: PlannerRequest,
        *,
        target_type: str,
    ) -> PlannerDecision:
        directive = request.shared_search or {}
        raw_action = directive.get("action", {})
        action = dict(raw_action) if isinstance(raw_action, Mapping) else {}
        phase = str(directive.get("phase", ""))
        if phase == "route_entry_alignment":
            reason_code = "shared_search_route_entry_alignment"
            rationale = (
                "Align with the precommitted route-entry heading using shared "
                "target-independent control state."
            )
        else:
            reason_code = "shared_search_coverage"
            rationale = (
                "Execute the next primitive action in the precommitted "
                "target-independent coverage route."
            )
        return self._decision(
            action,
            target_object_type=target_type,
            reason_code=reason_code,
            rationale=rationale,
        )

    def _approach_visible_book(
        self, request: PlannerRequest, book: Mapping[str, Any]
    ) -> PlannerDecision | None:
        return self._approach_visible_target(request, book, target_type="Book")

    def _approach_visible_target(
        self,
        request: PlannerRequest,
        target: Mapping[str, Any],
        *,
        target_type: str,
    ) -> PlannerDecision | None:
        current_position = _agent_vector(request.observation, "position")
        object_position = target.get("position")
        if not current_position or not isinstance(object_position, Mapping):
            return None
        dx = _number(object_position, "x") - _number(current_position, "x")
        dz = _number(object_position, "z") - _number(current_position, "z")
        if math.hypot(dx, dz) <= self.interaction_distance:
            return None
        current_rotation = _agent_vector(request.observation, "rotation")
        current_yaw = _number(current_rotation, "y")
        target_yaw = math.degrees(math.atan2(dx, dz)) % 360.0
        delta = _angle_delta(target_yaw, current_yaw)
        if abs(delta) > self.visible_target_rotation_tolerance_degrees:
            action = "RotateRight" if delta > 0 else "RotateLeft"
            return self._decision(
                {"action": action},
                target_object_type=target_type,
                reason_code="orient_to_visible_target",
                rationale=(
                    f"Rotate toward the currently visible {target_type} before "
                    "approaching it."
                ),
            )
        return self._decision(
            {"action": "MoveAhead"},
            target_object_type=target_type,
            reason_code="approach_visible_target",
            rationale=(
                f"Move closer to the currently visible {target_type} before interaction."
            ),
        )

    def _memory_navigation(
        self,
        request: PlannerRequest,
        record: Mapping[str, Any],
        *,
        target_type: str = "Book",
    ) -> PlannerDecision:
        record_id = str(record.get("record_id", ""))
        if _last_failed_move(request):
            return self._decision(
                {"action": "RotateRight"},
                target_object_type=target_type,
                memory_guided=True,
                memory_record_ids=(record_id,),
                reason_code="memory_navigation_obstacle_recovery",
                rationale=(
                    f"The last memory-guided move toward {target_type} failed; "
                    "rotate before retrying."
                ),
            )

        current_position = _agent_vector(request.observation, "position")
        target_position = record.get("last_seen_agent_position")
        if isinstance(target_position, Mapping) and current_position:
            dx = _number(target_position, "x") - _number(current_position, "x")
            dz = _number(target_position, "z") - _number(current_position, "z")
            distance = math.hypot(dx, dz)
            if distance > self.position_tolerance:
                current_rotation = _agent_vector(request.observation, "rotation")
                current_yaw = _number(current_rotation, "y")
                target_yaw = math.degrees(math.atan2(dx, dz)) % 360.0
                delta = _angle_delta(target_yaw, current_yaw)
                if abs(delta) > self.rotation_tolerance_degrees:
                    action = "RotateRight" if delta > 0 else "RotateLeft"
                    return self._decision(
                        {"action": action},
                        target_object_type=target_type,
                        memory_guided=True,
                        memory_record_ids=(record_id,),
                        reason_code="return_to_last_seen_position_heading",
                        rationale=(
                            f"Rotate toward the camera position stored when "
                            f"{target_type} was visible."
                        ),
                    )
                return self._decision(
                    {"action": "MoveAhead"},
                    target_object_type=target_type,
                    memory_guided=True,
                    memory_record_ids=(record_id,),
                    reason_code="return_to_last_seen_position",
                    rationale=(
                        f"Move toward the camera position stored when {target_type} "
                        "was visible."
                    ),
                )

        current_rotation = _agent_vector(request.observation, "rotation")
        target_rotation = record.get("last_seen_agent_rotation")
        if isinstance(target_rotation, Mapping):
            delta = _angle_delta(
                _number(target_rotation, "y"), _number(current_rotation, "y")
            )
            if abs(delta) > self.rotation_tolerance_degrees:
                action = "RotateRight" if delta > 0 else "RotateLeft"
                return self._decision(
                    {"action": action},
                    target_object_type=target_type,
                    memory_guided=True,
                    memory_record_ids=(record_id,),
                    reason_code="return_to_last_seen_viewpoint",
                    rationale=(
                        f"Restore the camera heading from {target_type}'s last "
                        "visible observation."
                    ),
                )

        agent = request.observation.get("agent", {})
        current_horizon = (
            float(agent.get("cameraHorizon", 0.0))
            if isinstance(agent, Mapping)
            and isinstance(agent.get("cameraHorizon", 0.0), (int, float))
            else 0.0
        )
        target_horizon = record.get("last_seen_camera_horizon")
        if isinstance(target_horizon, (int, float)):
            horizon_delta = float(target_horizon) - current_horizon
            if abs(horizon_delta) > self.horizon_tolerance_degrees:
                action = "LookDown" if horizon_delta > 0 else "LookUp"
                return self._decision(
                    {"action": action},
                    target_object_type=target_type,
                    memory_guided=True,
                    memory_record_ids=(record_id,),
                    reason_code="restore_last_seen_camera_horizon",
                    rationale=(
                        f"Restore the camera horizon from {target_type}'s last "
                        "visible observation."
                    ),
                )

        return self._decision(
            {"action": "RotateRight"},
            target_object_type=target_type,
            memory_guided=True,
            memory_record_ids=(record_id,),
            reason_code="search_near_last_seen_viewpoint",
            rationale=(
                f"The last-seen viewpoint was reached but {target_type} is not "
                "visible; scan locally."
            ),
        )

    def _decision(
        self,
        action: dict[str, Any],
        *,
        target_object_type: str | None = None,
        memory_guided: bool = False,
        memory_record_ids: tuple[str, ...] = (),
        reason_code: str,
        rationale: str,
    ) -> PlannerDecision:
        return PlannerDecision(
            action=action,
            target_object_type=target_object_type,
            memory_guided=memory_guided,
            memory_record_ids=memory_record_ids,
            reason_code=reason_code,
            rationale=rationale,
            planner_name=self.name,
        )


def validate_planner_decision(
    decision: PlannerDecision,
    request: PlannerRequest,
    *,
    action_space: ActionSpace | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Validate action schema, visible targets, and cited memory provenance."""

    errors: list[str] = []
    space = action_space or ActionSpace()
    valid, message = space.validate(decision.action)
    if not valid:
        errors.append(message)

    action_name = str(decision.action.get("action", ""))
    if action_name not in request.allowed_actions:
        errors.append(f"action_not_allowed_for_request:{action_name}")

    visible_ids = {
        str(obj.get("objectId"))
        for obj in _visible_objects(request)
        if obj.get("visible") is True and obj.get("objectId")
    }
    target_id = str(decision.action.get("objectId", ""))
    if target_id and target_id not in visible_ids:
        errors.append(f"target_not_currently_visible:{target_id}")

    retrieved_ids = {
        str(record.get("record_id", "")) for record in request.retrieved_memory
    }
    cited_ids = set(decision.memory_record_ids)
    if not cited_ids.issubset(retrieved_ids):
        errors.append("decision_cites_unretrieved_memory")
    if decision.memory_guided and not cited_ids:
        errors.append("memory_guided_without_record_id")
    if not decision.memory_guided and cited_ids:
        errors.append("memory_record_cited_without_memory_guided_flag")
    if not decision.reason_code.strip():
        errors.append("missing_reason_code")
    if not decision.rationale.strip():
        errors.append("missing_rationale")
    if request.shared_search is not None:
        expected = request.shared_search.get("action")
        if not isinstance(expected, Mapping) or dict(decision.action) != dict(expected):
            errors.append("decision_diverges_from_shared_search_directive")
        if decision.memory_guided or decision.memory_record_ids:
            errors.append("shared_search_decision_cannot_be_memory_guided")
        if not decision.reason_code.startswith("shared_search_"):
            errors.append("shared_search_reason_code_missing")
    return not errors, tuple(errors)


@dataclass(frozen=True)
class ExternalPlannerCall:
    """Safe call metadata retained without prompts, secrets, or hidden state."""

    response_id: str | None
    model: str
    attempt_count: int
    request_character_count: int
    input_tokens: int | None
    output_tokens: int | None


class OpenAICompatiblePlanner:
    """Optional Responses-API structured planner over the safe request only."""

    name = "openai_compatible_structured"

    def __init__(
        self,
        *,
        model: str = "gpt-5.6",
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 60.0,
        max_attempts: int = 2,
        client: Any | None = None,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self._client = client
        self.last_call: ExternalPlannerCall | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise PlannerOutputError(
                "OPENAI_API_KEY is not set; use the deterministic planner or configure the optional LLM path"
            )
        try:
            from openai import OpenAI
        except (ImportError, ModuleNotFoundError) as exc:
            raise PlannerOutputError(
                "the optional 'llm' dependencies are not installed"
            ) from exc
        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout_seconds,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)
        return self._client

    @staticmethod
    def _decision_model() -> Any:
        try:
            from pydantic import BaseModel, ConfigDict, Field
        except (ImportError, ModuleNotFoundError) as exc:
            raise PlannerOutputError(
                "Pydantic is required for structured planner output"
            ) from exc

        class DecisionModel(BaseModel):
            model_config = ConfigDict(extra="forbid")

            action_name: str
            object_id: str | None = None
            target_object_type: str | None = None
            memory_guided: bool
            memory_record_ids: list[str] = Field(default_factory=list)
            reason_code: str
            rationale: str

        return DecisionModel

    def plan(self, request: PlannerRequest) -> PlannerDecision:
        client = self._get_client()
        decision_model = self._decision_model()
        request_json = json.dumps(
            request.snapshot(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            retry_note = (
                ""
                if not last_error
                else f"\nThe prior output was rejected for: {last_error}. Correct it."
            )
            try:
                response = client.responses.parse(
                    model=self.model,
                    input=[
                        {
                            "role": "system",
                            "content": (
                                "Select exactly one embodied action using only the supplied "
                                "planner request. Never infer or request hidden global state. "
                                "An objectId may be used only when it is currently visible. "
                                "Cite memory_record_ids only when the action actually uses those "
                                "retrieved records. Keep rationale to one short audit sentence."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Planner request JSON:\n{request_json}{retry_note}",
                        },
                    ],
                    text_format=decision_model,
                )
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                continue

            parsed = getattr(response, "output_parsed", None)
            if parsed is None:
                last_error = "response contained no parsed structured output"
                continue
            data = parsed.model_dump()
            action = {"action": str(data["action_name"])}
            if data.get("object_id"):
                action["objectId"] = str(data["object_id"])
            decision = PlannerDecision(
                action=action,
                target_object_type=data.get("target_object_type"),
                memory_guided=bool(data["memory_guided"]),
                memory_record_ids=tuple(map(str, data.get("memory_record_ids", []))),
                reason_code=str(data["reason_code"]),
                rationale=str(data["rationale"]),
                planner_name=self.name,
                raw_response_id=str(getattr(response, "id", "")) or None,
            )
            valid, errors = validate_planner_decision(decision, request)
            if not valid:
                last_error = "; ".join(errors)
                continue

            usage = getattr(response, "usage", None)
            self.last_call = ExternalPlannerCall(
                response_id=decision.raw_response_id,
                model=self.model,
                attempt_count=attempt,
                request_character_count=len(request_json),
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
            )
            return decision

        raise PlannerOutputError(
            f"structured planner failed after {self.max_attempts} attempts: {last_error}"
        )


def build_structured_planner(
    name: str,
    *,
    model: str = "gpt-5.6",
    base_url: str | None = None,
) -> StructuredPlanner:
    """Build the requested planner without making an API call."""

    if name == "deterministic":
        return ThorBookReacquirePlanner()
    if name == "openai_compatible":
        return OpenAICompatiblePlanner(model=model, base_url=base_url)
    raise ValueError(f"unsupported Phase 4 planner: {name}")

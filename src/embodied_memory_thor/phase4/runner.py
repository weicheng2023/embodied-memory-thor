"""One real-THOR episode engine shared by formal and debug presentations."""

from __future__ import annotations

import math
import os
import subprocess
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping

from embodied_memory_thor.actions import ActionExecutor, ActionSpace
from embodied_memory_thor.env import EmbodiedEnv, ThorEnv
from embodied_memory_thor.evaluation import evaluate_task_success, load_task
from embodied_memory_thor.phase4.contracts import (
    EVALUATOR_ONLY_LABEL,
    RGB_BOUNDARY_LABEL,
    TRACE_SCHEMA_VERSION,
    PlannerInputAudit,
    PlannerRequest,
    audit_planner_request,
    build_planner_observation,
    memory_snapshot_diff,
    stable_digest,
    visible_object_ids,
)
from embodied_memory_thor.phase4.planners import (
    THOR_BOOK_ACTIONS,
    THOR_CUP_COFFEE_ACTIONS,
    StructuredPlanner,
    build_structured_planner,
    validate_planner_decision,
)
from embodied_memory_thor.phase4.spatial_memory import (
    ThorMemoryProvider,
    build_thor_memory,
)
from embodied_memory_thor.phase4.task import (
    BookReacquireProgress,
    CupAfterCoffeeProgress,
    PHASE5_BOOK_DISTRACTION_POLICY_V1,
    PHASE5_BOOK_DISTRACTION_POLICY_V2,
)
from embodied_memory_thor.phase4.trace import (
    LiveFrameViewer,
    ThorTraceWriter,
    file_sha256,
    render_console_step,
    rgb_array_diagnostics,
)
from embodied_memory_thor.phase5.interventions import (
    EvaluatorEpisodeSetup,
    EvaluatorIntervention,
)
from embodied_memory_thor.phase5.memory_navigation import (
    MEMORY_NAVIGATION_POLICY_VERSION,
    MEMORY_NAVIGATION_ROTATION_STEP_DEGREES,
    MemoryNavigationGuard,
)
from embodied_memory_thor.phase5.search import (
    FrozenSearchRoute,
    FrozenSearchRouteState,
    SHARED_SEARCH_ENTRY_RECOVERY_ACTION_LIMIT,
    SHARED_SEARCH_ENTRY_RECOVERY_POLICY_VERSION,
    SearchRouteError,
    load_frozen_search_route,
)
from embodied_memory_thor.phase5.target_lock import (
    TARGET_LOCK_APPROACH_ACTION_BUDGET,
    TARGET_LOCK_POLICY_VERSION,
    TARGET_LOCK_RECOVERY_ACTION_BUDGET,
    SharedTargetLockPolicy,
)
from embodied_memory_thor.utils.serialization import to_jsonable


PHASE4_PROTOCOL_VERSION = "phase4-v3"
PHASE4_TASKS_PATH = Path(__file__).resolve().parents[3] / "configs" / "phase4_tasks.yaml"
SUPPORTED_REAL_TASKS = {
    "thor_book_reacquire",
    "thor_book_reacquire_k2",
    "thor_cup_after_coffee_subgoal",
}
THOR_BOOK_SETUP_ACTIONS: tuple[dict[str, str], ...] = (
    {"action": "RotateRight"},
    {"action": "MoveAhead"},
    {"action": "RotateRight"},
)


@dataclass(frozen=True)
class _TaskRuntimeSpec:
    initial_target_type: str
    retrieval_target_type: str
    setup_actions: tuple[dict[str, str], ...]
    allowed_actions: tuple[str, ...]


def _task_runtime_spec(task_name: str) -> _TaskRuntimeSpec:
    if task_name in {"thor_book_reacquire", "thor_book_reacquire_k2"}:
        return _TaskRuntimeSpec(
            initial_target_type="Book",
            retrieval_target_type="Book",
            setup_actions=THOR_BOOK_SETUP_ACTIONS,
            allowed_actions=THOR_BOOK_ACTIONS,
        )
    if task_name == "thor_cup_after_coffee_subgoal":
        return _TaskRuntimeSpec(
            initial_target_type="Cup",
            retrieval_target_type="Cup",
            setup_actions=(),
            allowed_actions=THOR_CUP_COFFEE_ACTIONS,
        )
    raise ValueError(f"unsupported real task: {task_name}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")


def default_thor_output_dir(
    *, task: str, planner: str, mode: str, root: str | Path = "outputs/thor_runs"
) -> Path:
    episode_id = f"{task}__{planner}__{mode}"
    return (Path(root) / _timestamp_slug() / episode_id).resolve()


def _git_state() -> dict[str, Any]:
    """Return reproducibility metadata without making Git a runtime dependency."""

    project_root = Path(__file__).resolve().parents[3]
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return {"code_revision": revision, "working_tree_dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"code_revision": "unavailable", "working_tree_dirty": None}


@dataclass(frozen=True)
class ThorEpisodeConfig:
    """Frozen settings for one Phase 4 episode."""

    task: str = "thor_book_reacquire"
    scene: str = "FloorPlan1"
    planner: str = "deterministic"
    memory: str = "object_memory"
    book_distraction_policy: str = PHASE5_BOOK_DISTRACTION_POLICY_V1
    subgoal_route_id: str | None = None
    search_route_id: str | None = None
    condition: str = "stable"
    mode: str = "formal"
    max_steps: int = 12
    output_dir: Path | None = None
    save_frames: bool = False
    trace_html: bool = True
    visualize: bool = False
    step_delay: float = 0.0
    save_evaluator_debug: bool = False
    included_in_formal_aggregate: bool | None = None
    run_purpose: str = "single_episode"
    model: str = "gpt-5.6"
    base_url: str | None = None
    controller_settings: dict[str, Any] = field(
        default_factory=lambda: {
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
    )

    def validate(self) -> None:
        if self.task not in SUPPORTED_REAL_TASKS:
            raise ValueError(f"unsupported real task: {self.task}")
        if not self.scene.strip():
            raise ValueError("scene must be non-empty")
        if self.planner not in {"deterministic", "openai_compatible"}:
            raise ValueError(f"unsupported planner: {self.planner}")
        if self.memory not in {"no_memory", "short_memory_k2", "object_memory"}:
            raise ValueError(f"unsupported memory mode: {self.memory}")
        if self.book_distraction_policy not in {
            PHASE5_BOOK_DISTRACTION_POLICY_V1,
            PHASE5_BOOK_DISTRACTION_POLICY_V2,
        }:
            raise ValueError("unsupported Book distraction policy")
        if (
            self.task != "thor_book_reacquire_k2"
            and self.book_distraction_policy != PHASE5_BOOK_DISTRACTION_POLICY_V1
        ):
            raise ValueError(
                "Book distraction successor applies only to the Phase 5 R1 task"
            )
        if self.search_route_id is not None:
            if not self.search_route_id.strip():
                raise ValueError("search_route_id cannot be empty")
            if self.planner != "deterministic":
                raise ValueError("frozen search routes require the deterministic planner")
            if self.task not in {
                "thor_book_reacquire_k2",
                "thor_cup_after_coffee_subgoal",
            }:
                raise ValueError(
                    "frozen search routes require a Phase 5 comparison task"
                )
        if self.subgoal_route_id is not None:
            if not self.subgoal_route_id.strip():
                raise ValueError("subgoal_route_id cannot be empty")
            if self.planner != "deterministic":
                raise ValueError("frozen subgoal routes require the deterministic planner")
            if self.task != "thor_cup_after_coffee_subgoal":
                raise ValueError("frozen subgoal routes require the ordered R2 task")
        if self.task == "thor_cup_after_coffee_subgoal" and (
            (self.search_route_id is None) != (self.subgoal_route_id is None)
        ):
            raise ValueError(
                "ordered R2 frozen execution requires both subgoal and fallback routes"
            )
        if self.condition not in {"stable", "stale_r1"}:
            raise ValueError(f"unsupported condition: {self.condition}")
        if self.condition == "stale_r1" and self.task != "thor_book_reacquire_k2":
            raise ValueError("stale_r1 requires thor_book_reacquire_k2")
        if self.mode not in {"formal", "debug"}:
            raise ValueError("mode must be formal or debug")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.step_delay < 0:
            raise ValueError("step_delay cannot be negative")
        if not self.run_purpose.strip():
            raise ValueError("run_purpose must be non-empty")
        if self.visualize and self.mode != "debug":
            raise ValueError("--visualize is available only in debug mode")
        if self.step_delay and not self.visualize:
            raise ValueError("step_delay requires visualize=true")


class ThorEpisodeRunner:
    """Execute one planner-memory-action loop without a second debug code path."""

    def __init__(
        self,
        config: ThorEpisodeConfig,
        *,
        env: EmbodiedEnv | None = None,
        planner: StructuredPlanner | None = None,
        memory: ThorMemoryProvider | None = None,
        intervention: EvaluatorIntervention | None = None,
        search_route: FrozenSearchRoute | None = None,
        subgoal_route: FrozenSearchRoute | None = None,
        evaluator_setup: EvaluatorEpisodeSetup | None = None,
        viewer_factory: Callable[..., LiveFrameViewer] | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self.env = env or ThorEnv(controller_kwargs=config.controller_settings)
        self.planner = planner or build_structured_planner(
            config.planner,
            model=config.model,
            base_url=config.base_url,
            memory_rotation_step_degrees=float(
                config.controller_settings.get("rotateStepDegrees", 90)
            ),
        )
        self.memory = memory or build_thor_memory(config.memory)
        if subgoal_route is not None and config.subgoal_route_id != subgoal_route.route_id:
            raise ValueError("injected subgoal route does not match subgoal_route_id")
        self.subgoal_route = subgoal_route
        if self.subgoal_route is None and config.subgoal_route_id is not None:
            self.subgoal_route = load_frozen_search_route(config.subgoal_route_id)
        if self.subgoal_route is not None:
            self.subgoal_route.validate()
            if self.subgoal_route.task != config.task:
                raise ValueError("frozen subgoal route task does not match episode task")
            if self.subgoal_route.scene != config.scene:
                raise ValueError("frozen subgoal route scene does not match episode scene")
            if self.subgoal_route.route_role != "task_subgoal_navigation":
                raise ValueError("frozen subgoal route has the wrong route role")
        if search_route is not None and config.search_route_id != search_route.route_id:
            raise ValueError("injected search route does not match search_route_id")
        self.search_route = search_route
        if self.search_route is None and config.search_route_id is not None:
            self.search_route = load_frozen_search_route(config.search_route_id)
        if self.search_route is not None:
            self.search_route.validate()
            if self.search_route.task != config.task:
                raise ValueError("frozen search route task does not match episode task")
            if self.search_route.scene != config.scene:
                raise ValueError("frozen search route scene does not match episode scene")
            if self.search_route.route_role != "target_independent_fallback":
                raise ValueError("frozen search route has the wrong route role")
        if config.condition == "stale_r1" and intervention is None:
            raise ValueError("stale_r1 requires an evaluator intervention")
        if config.condition == "stable" and intervention is not None:
            raise ValueError("an evaluator intervention requires condition=stale_r1")
        self.intervention = intervention
        self.evaluator_setup = evaluator_setup
        if self.evaluator_setup is not None:
            reference = self.evaluator_setup.public_reference()
            if str(reference.get("scene", "")) != config.scene:
                raise ValueError("evaluator setup scene does not match episode scene")
            if config.task not in {
                "thor_book_reacquire_k2",
                "thor_cup_after_coffee_subgoal",
            }:
                raise ValueError(
                    "frozen evaluator setup requires a Phase 5 comparison task"
                )
        self.action_space = ActionSpace()
        self.executor = ActionExecutor(self.action_space)
        self.viewer_factory = viewer_factory or LiveFrameViewer

    def run(self) -> dict[str, Any]:
        config = self.config
        task = load_task(config.task, PHASE4_TASKS_PATH)
        runtime_spec = _task_runtime_spec(config.task)
        output_dir = config.output_dir or default_thor_output_dir(
            task=config.task, planner=config.planner, mode=config.mode
        )
        writer = ThorTraceWriter(
            output_dir,
            evaluator_debug=config.save_evaluator_debug,
            intervention_log=self.intervention is not None,
            private_setup_log=self.evaluator_setup is not None,
        )
        episode_id = writer.output_dir.name
        manifest = {
            "protocol_version": PHASE4_PROTOCOL_VERSION,
            "trace_schema_version": TRACE_SCHEMA_VERSION,
            "episode_id": episode_id,
            "created_at": _utc_now(),
            "task": config.task,
            "scene": config.scene,
            "planner": config.planner,
            "memory": config.memory,
            "book_distraction_policy": config.book_distraction_policy,
            "subgoal_route": (
                self.subgoal_route.public_reference()
                if self.subgoal_route is not None
                else None
            ),
            "search_route": (
                self.search_route.public_reference()
                if self.search_route is not None
                else None
            ),
            "condition": config.condition,
            "mode": config.mode,
            "max_steps": config.max_steps,
            "controller_settings": deepcopy(config.controller_settings),
            "save_frames": config.save_frames,
            "trace_html": config.trace_html,
            "visualize": config.visualize,
            "step_delay": config.step_delay,
            "visualization_policy": {
                "process_isolation": True,
                "viewer_failure_changes_episode_semantics": False,
                "fallback": "continue_with_configured_non_gui_artifacts",
                "native_stderr_captured_separately": True,
            },
            "save_evaluator_debug": config.save_evaluator_debug,
            "included_in_formal_aggregate": config.included_in_formal_aggregate,
            "run_purpose": config.run_purpose,
            "task_setup": {
                "policy": (
                    "fixed_planner_independent_visible_observation_sequence"
                    if runtime_spec.setup_actions
                    else "qualified_initial_visible_observation_required"
                ),
                "initial_target_type": runtime_spec.initial_target_type,
                "actions": deepcopy(runtime_spec.setup_actions),
                "uses_evaluator_metadata": False,
                "included_in_planner_metrics": False,
                "desktop_screenshots_used": False,
                "rgb_diagnostic": "in_memory_array_statistics_and_raw_hash",
            },
            "rgb_consumed_by_planner": False,
            "rgb_boundary_label": RGB_BOUNDARY_LABEL,
            "evaluator_boundary_label": EVALUATOR_ONLY_LABEL,
            "evidence_level": "E2",
            "claim_boundary": (
                "controlled live closed-loop and information-flow evidence; "
                "not a memory-improvement comparison"
            ),
            **_git_state(),
        }
        if self.evaluator_setup is not None:
            manifest["frozen_configuration"] = dict(
                self.evaluator_setup.public_reference()
            )
        if self.search_route is not None:
            manifest["shared_search_policy"] = {
                "same_route_available_to_all_memory_variants": True,
                "route_entry_pose_source": (
                    "planner_safe_observation_0_agent_pose_only"
                ),
                "target_object_history_retained": False,
                "route_coordinates_in_planner_input": False,
                "route_action_failure_policy": "invalidate_episode",
                "entry_recovery_policy": (
                    SHARED_SEARCH_ENTRY_RECOVERY_POLICY_VERSION
                ),
                "entry_recovery_action_limit": (
                    SHARED_SEARCH_ENTRY_RECOVERY_ACTION_LIMIT
                ),
                "entry_recovery_input": (
                    "successful planner action names only; no target, memory, "
                    "anchor, support, candidate outcome, or route coordinates"
                ),
                "same_entry_recovery_for_all_memory_variants": True,
            }
        if self.subgoal_route is not None:
            manifest["shared_subgoal_policy"] = {
                "same_route_available_to_all_memory_variants": True,
                "route_entry_pose_source": "planner_safe_observation_0_agent_pose_only",
                "target_coordinates_in_planner_input": False,
                "route_action_failure_policy": "invalidate_episode",
            }
        if config.task in {
            "thor_book_reacquire_k2",
            "thor_cup_after_coffee_subgoal",
        }:
            manifest["target_lock_policy"] = {
                "policy": TARGET_LOCK_POLICY_VERSION,
                "same_policy_for_all_memory_variants": True,
                "planner_safe_observation_only": True,
                "recovery_action_budget": TARGET_LOCK_RECOVERY_ACTION_BUDGET,
                "approach_action_budget": TARGET_LOCK_APPROACH_ACTION_BUDGET,
                "evaluator_coordinates_consumed": False,
            }
            manifest["memory_navigation_policy"] = {
                "policy": MEMORY_NAVIGATION_POLICY_VERSION,
                "rotation_step_degrees": MEMORY_NAVIGATION_ROTATION_STEP_DEGREES,
                "uses_planner_safe_observations_only": True,
                "same_escape_policy_for_all_memory_variants": True,
                "fallback_after_bounded_nonprogress": True,
            }
        if self.intervention is not None:
            manifest["intervention"] = {
                "intervention_id": self.intervention.intervention_id,
                "boundary": EVALUATOR_ONLY_LABEL,
                "included_in_planner_metrics": False,
                "destination_visible_to_planner": False,
            }
        manifest["evidence_status"] = (
            "development_only"
            if manifest["working_tree_dirty"] is not False or config.mode != "formal"
            else (
                "excluded_engineering_probe"
                if config.included_in_formal_aggregate is False
                else "formal_acceptance_candidate"
            )
        )
        if config.planner == "openai_compatible":
            manifest["external_planner"] = {
                "model": config.model,
                "base_url_configured": bool(
                    config.base_url or os.environ.get("OPENAI_BASE_URL")
                ),
                "api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
            }
        writer.write_manifest(manifest)

        if config.task == "thor_book_reacquire_k2":
            progress = (
                BookReacquireProgress.phase5_k2_v2()
                if config.book_distraction_policy
                == PHASE5_BOOK_DISTRACTION_POLICY_V2
                else BookReacquireProgress.phase5_k2()
            )
        elif config.task == "thor_cup_after_coffee_subgoal":
            progress = CupAfterCoffeeProgress()
        else:
            progress = BookReacquireProgress()
        visible_history: dict[str, set[str]] = {}
        action_history: list[dict[str, Any]] = []
        planning_latencies: list[float] = []
        action_latencies: list[float] = []
        artifact_latencies: list[float] = []
        information_boundary_passed = True
        invalid_action_count = 0
        memory_guided_action_count = 0
        memory_retrieval_count = 0
        useful_memory_retrieval_count = 0
        short_memory_evicted_before_reacquisition = False
        translation_action_count = 0
        translation_distance_meters = 0.0
        search_rotation_count = 0
        repeated_viewpoint_visit_count = 0
        visited_viewpoints: set[tuple[float, ...]] = set()
        failed_interaction_count = 0
        failure_taxonomy: dict[str, int] = {}
        stale_memory_use_count = 0
        old_viewpoint_miss_count = 0
        stale_record_recovery_count = 0
        fallback_action_count_after_stale_miss = 0
        stale_fallback_active = False
        stale_rediscovery_step: int | None = None
        memory_correction_step: int | None = None
        intervention_count = 0
        intervention_failure_count = 0
        planner_call_count = 0
        shared_search_alignment_action_count = 0
        shared_search_entry_recovery_action_count = 0
        shared_search_entry_recovery_record_failure_count = 0
        shared_search_coverage_action_count = 0
        shared_search_route_entry_mismatch_count = 0
        shared_search_route_exhausted_count = 0
        shared_search_action_failure_count = 0
        search_route_state: FrozenSearchRouteState | None = None
        shared_subgoal_alignment_action_count = 0
        shared_subgoal_coverage_action_count = 0
        shared_subgoal_route_entry_mismatch_count = 0
        shared_subgoal_route_exhausted_count = 0
        shared_subgoal_action_failure_count = 0
        subgoal_route_state: FrozenSearchRouteState | None = None
        target_lock_policy = (
            SharedTargetLockPolicy(target_type=runtime_spec.retrieval_target_type)
            if config.task in {
                "thor_book_reacquire_k2",
                "thor_cup_after_coffee_subgoal",
            }
            else None
        )
        memory_navigation_guard = MemoryNavigationGuard()
        setup_action_count = 0
        setup_action_latencies: list[float] = []
        setup_completed = False
        setup_failure_reason = ""
        steps = 0
        success = False
        failure_reason = ""
        viewer: LiveFrameViewer | None = None
        visualization_requested = config.visualize
        visualization_started = False
        visualization_available = False
        visualization_failure_reason = ""
        visualization_user_stopped = False
        visualization_displayed_frame_count = 0
        episode_continued_after_viewer_failure = False
        episode_continued_after_viewer_stop = False
        visualization_diagnostic_path = (
            writer.output_dir / "visualization_stderr.log"
            if config.visualize
            else None
        )
        episode_started = perf_counter()

        try:
            if config.visualize:
                try:
                    viewer = self.viewer_factory(
                        diagnostic_log=visualization_diagnostic_path
                    )
                    startup_status = viewer.startup_status
                    visualization_started = bool(startup_status.available)
                    visualization_available = bool(startup_status.available)
                    if not startup_status.available:
                        visualization_failure_reason = (
                            startup_status.failure_reason
                            or "viewer_unavailable_at_startup"
                        )
                        print(
                            "Visualization unavailable; continuing the episode "
                            f"without a live viewer: {visualization_failure_reason}"
                        )
                        episode_continued_after_viewer_failure = True
                        viewer.close()
                        viewer = None
                except Exception as exc:
                    visualization_failure_reason = (
                        f"viewer_initialization_error:{type(exc).__name__}:{exc}"
                    )
                    print(
                        "Visualization initialization failed; continuing the "
                        f"episode without a live viewer: {visualization_failure_reason}"
                    )
                    episode_continued_after_viewer_failure = True
                    viewer = None

            self.env.reset(config.scene)
            reset_observation = build_planner_observation(
                self.env.get_observation()
            )
            setup_initial_observation = None
            if self.evaluator_setup is not None:
                private_setup_record = self.evaluator_setup.apply(
                    env=self.env,
                    task_name=config.task,
                    scene=config.scene,
                )
                writer.log_private_setup(private_setup_record)
                if private_setup_record.get("success") is not True:
                    private_error = str(
                        private_setup_record.get("private_error", "")
                        or "frozen evaluator setup failed"
                    )
                    raise RuntimeError(private_error)
                setup_initial_observation = build_planner_observation(
                    self.env.get_observation()
                )
                for safe_action_field in (
                    "last_action",
                    "last_action_success",
                    "last_action_error",
                ):
                    setup_initial_observation[safe_action_field] = deepcopy(
                        reset_observation.get(safe_action_field)
                    )
            (
                current_observation,
                setup_completed,
                setup_failure_reason,
                setup_action_count,
                setup_action_latencies,
            ) = self._run_task_setup(
                writer,
                runtime_spec,
                initial_observation=setup_initial_observation,
            )
            progress.initialize(current_observation)
            visible_history["observation:0"] = set(visible_object_ids(current_observation))
            self.memory.observe(
                current_observation, step=0, observation_id="observation:0"
            )
            if self.search_route is not None and config.task != "thor_cup_after_coffee_subgoal":
                search_route_state = FrozenSearchRouteState(
                    self.search_route,
                    initial_observation=current_observation,
                )
            if self.subgoal_route is not None:
                subgoal_route_state = FrozenSearchRouteState(
                    self.subgoal_route,
                    initial_observation=current_observation,
                )
            initial_viewpoint = self._viewpoint_key(current_observation)
            if initial_viewpoint is not None:
                visited_viewpoints.add(initial_viewpoint)

            evaluator_state = self.env.get_evaluator_state()
            writer.log_evaluator_state(step=0, metadata=evaluator_state)
            if setup_failure_reason:
                failure_reason = setup_failure_reason
            elif progress.preflight_error:
                failure_reason = progress.preflight_error
            else:
                initial_success = evaluate_task_success(task, evaluator_state)
                success = initial_success.success

            for step in range(1, config.max_steps + 1):
                if success or failure_reason:
                    break
                progress.observe_before_action(current_observation, step=step)
                if progress.stage in {"preflight_failed", "distraction_failed"}:
                    failure_reason = progress.stage
                    break

                steps = step
                if (
                    config.task == "thor_cup_after_coffee_subgoal"
                    and progress.stage in {"reacquire_cup", "pickup_cup"}
                    and self.search_route is not None
                    and search_route_state is None
                ):
                    search_route_state = FrozenSearchRouteState(
                        self.search_route,
                        initial_observation=current_observation,
                    )
                memory_before = self.memory.snapshot()
                raw_retrieved = tuple(
                    self.memory.retrieve(runtime_spec.retrieval_target_type)
                )
                memory_retrieval_count += len(raw_retrieved)
                retrieved = memory_navigation_guard.filter_retrieved(raw_retrieved)
                if (
                    config.memory == "short_memory_k2"
                    and progress.stage in {"reacquire_book", "reacquire_cup"}
                    and not retrieved
                ):
                    short_memory_evicted_before_reacquisition = True
                shared_search = None
                active_route_state = None
                active_route = None
                active_route_kind = None
                target_lock = None
                if (
                    target_lock_policy is not None
                    and progress.stage
                    in {"reacquire_book", "pickup_book", "reacquire_cup", "pickup_cup"}
                ):
                    target_lock = target_lock_policy.next_directive(
                        current_observation,
                        allowed_actions=runtime_spec.allowed_actions,
                    )
                if (
                    target_lock is None
                    and subgoal_route_state is not None
                    and progress.stage == "toggle_coffee_machine"
                    and not subgoal_route_state.complete
                ):
                    try:
                        shared_search = subgoal_route_state.next_directive(
                            current_observation
                        )
                        active_route_state = subgoal_route_state
                        active_route = self.subgoal_route
                        active_route_kind = "subgoal"
                    except SearchRouteError as exc:
                        if str(exc) == "frozen search route exhausted":
                            shared_subgoal_route_exhausted_count += 1
                        else:
                            shared_subgoal_route_entry_mismatch_count += 1
                        failure_reason = f"shared_subgoal_unavailable:{exc}"
                        break
                if (
                    target_lock is None
                    and shared_search is None
                    and subgoal_route_state is not None
                    and subgoal_route_state.complete
                    and progress.stage == "toggle_coffee_machine"
                    and not self._visible_target(current_observation, "CoffeeMachine")
                ):
                    failure_reason = "shared_subgoal_completion_target_missing"
                    break
                if (
                    target_lock is None
                    and shared_search is None
                    and search_route_state is not None
                    and progress.stage in {"reacquire_book", "reacquire_cup"}
                    and not retrieved
                ):
                    try:
                        shared_search = search_route_state.next_directive(
                            current_observation
                        )
                        active_route_state = search_route_state
                        active_route = self.search_route
                        active_route_kind = "fallback"
                    except SearchRouteError as exc:
                        if str(exc) == "frozen search route exhausted":
                            shared_search_route_exhausted_count += 1
                        else:
                            shared_search_route_entry_mismatch_count += 1
                        failure_reason = f"shared_search_unavailable:{exc}"
                        break
                request = PlannerRequest(
                    task_name=task.task_name,
                    instruction=task.natural_language_instruction,
                    task_stage=progress.stage,
                    step=step,
                    max_steps=config.max_steps,
                    observation=deepcopy(current_observation),
                    allowed_actions=runtime_spec.allowed_actions,
                    retrieved_memory=retrieved,
                    recent_action_results=tuple(deepcopy(action_history[-5:])),
                    shared_search=deepcopy(shared_search),
                    target_lock=deepcopy(target_lock),
                )
                audit = self._audit_with_provenance(
                    audit_planner_request(request), request, visible_history
                )
                information_boundary_passed = information_boundary_passed and audit.passed

                artifact_started = perf_counter()
                frame_record, pre_action_frame = self._capture_pre_action_frame(
                    writer, step=step
                )
                artifact_latencies.append(perf_counter() - artifact_started)

                planning_started = perf_counter()
                try:
                    decision = self.planner.plan(request)
                except Exception as exc:
                    planning_latency = perf_counter() - planning_started
                    planning_latencies.append(planning_latency)
                    planner_call_count += 1
                    failure_reason = f"planner_error:{type(exc).__name__}:{exc}"
                    break
                planning_latency = perf_counter() - planning_started
                planning_latencies.append(planning_latency)
                planner_call_count += 1

                valid_decision, decision_errors = validate_planner_decision(
                    decision, request, action_space=self.action_space
                )
                if not valid_decision:
                    information_boundary_passed = False
                    invalid_action_count += 1
                    failure_reason = "invalid_planner_decision:" + ";".join(decision_errors)
                    break
                if decision.memory_guided:
                    memory_guided_action_count += 1
                    useful_memory_retrieval_count += 1
                    if config.condition == "stale_r1":
                        stale_memory_use_count += 1
                elif stale_fallback_active:
                    fallback_action_count_after_stale_miss += 1

                action_started = perf_counter()
                execution = self.executor.execute(self.env, decision.action)
                action_latency = perf_counter() - action_started
                action_latencies.append(action_latency)
                if (
                    search_route_state is not None
                    and search_route_state.coverage_cursor == 0
                    and shared_search is None
                    and request.task_stage
                    in {
                        "reacquire_book",
                        "pickup_book",
                        "reacquire_cup",
                        "pickup_cup",
                    }
                ):
                    try:
                        search_route_state.record_entry_departure_action(
                            action=execution.action,
                            success=execution.success,
                        )
                    except SearchRouteError as exc:
                        shared_search_entry_recovery_record_failure_count += 1
                        failure_reason = (
                            f"shared_search_entry_recovery_unavailable:{exc}"
                        )
                if shared_search is not None and active_route_state is not None:
                    if active_route_kind == "subgoal":
                        if shared_search.get("phase") == "route_entry_alignment":
                            shared_subgoal_alignment_action_count += 1
                        elif shared_search.get("phase") == "coverage":
                            shared_subgoal_coverage_action_count += 1
                    else:
                        if shared_search.get("phase") == "route_entry_alignment":
                            shared_search_alignment_action_count += 1
                        elif shared_search.get("phase") == "route_entry_recovery":
                            shared_search_entry_recovery_action_count += 1
                        elif shared_search.get("phase") == "coverage":
                            shared_search_coverage_action_count += 1
                    try:
                        active_route_state.record_result(
                            shared_search,
                            action=execution.action,
                            success=execution.success,
                        )
                    except SearchRouteError as exc:
                        if active_route_kind == "subgoal":
                            shared_subgoal_action_failure_count += 1
                            failure_reason = f"shared_subgoal_action_failed:{exc}"
                        else:
                            shared_search_action_failure_count += 1
                            failure_reason = f"shared_search_action_failed:{exc}"
                if execution.invalid_action:
                    invalid_action_count += 1
                action_name = str(execution.action.get("action", ""))
                if (
                    action_name in {"RotateLeft", "RotateRight"}
                    and "search" in decision.reason_code
                    and decision.reason_code
                    != "shared_search_route_entry_alignment"
                ):
                    search_rotation_count += 1
                if (
                    action_name in self.action_space.object_actions
                    and not execution.success
                ):
                    failed_interaction_count += 1
                    failure_key = execution.error_message.strip() or "unspecified_failure"
                    failure_taxonomy[failure_key] = failure_taxonomy.get(failure_key, 0) + 1

                pre_intervention_observation = build_planner_observation(
                    self.env.get_observation()
                )
                intervention_record = None
                if self.intervention is not None:
                    intervention_record = self.intervention.maybe_apply(
                        env=self.env,
                        task_name=config.task,
                        step=step,
                        task_stage=request.task_stage,
                        agent_action=execution.action,
                        agent_action_success=execution.success,
                        pre_intervention_observation=pre_intervention_observation,
                    )
                if intervention_record is not None:
                    intervention_count += 1
                    writer.log_intervention(intervention_record)
                    if intervention_record.get("success") is not True:
                        intervention_failure_count += 1
                        failure_reason = "evaluator_intervention_failed"
                    current_observation = build_planner_observation(
                        self.env.get_observation()
                    )
                    for safe_action_field in (
                        "last_action",
                        "last_action_success",
                        "last_action_error",
                    ):
                        current_observation[safe_action_field] = deepcopy(
                            pre_intervention_observation.get(safe_action_field)
                        )
                else:
                    current_observation = pre_intervention_observation
                memory_navigation_suppressed_ids = (
                    memory_navigation_guard.record_result(
                        memory_guided=decision.memory_guided,
                        record_ids=decision.memory_record_ids,
                        observation_before=request.observation,
                        observation_after=current_observation,
                    )
                )
                if target_lock is not None and target_lock_policy is not None:
                    target_lock_policy.record_result(
                        target_lock,
                        success=execution.success,
                        error_message=execution.error_message,
                        observation_after=current_observation,
                        allowed_actions=runtime_spec.allowed_actions,
                    )
                if execution.success and action_name in {
                    "MoveAhead",
                    "MoveBack",
                    "MoveLeft",
                    "MoveRight",
                }:
                    moved = self._translation_distance(
                        request.observation, current_observation
                    )
                    if moved is not None:
                        translation_action_count += 1
                        translation_distance_meters += moved
                viewpoint = self._viewpoint_key(current_observation)
                if viewpoint is not None:
                    if viewpoint in visited_viewpoints:
                        repeated_viewpoint_visit_count += 1
                    visited_viewpoints.add(viewpoint)
                post_observation_id = f"observation:{step}"
                visible_history[post_observation_id] = set(
                    visible_object_ids(current_observation)
                )
                progress.observe_action(
                    step=step,
                    action=decision.action,
                    success=execution.success,
                    observation_after=current_observation,
                )
                stale_ids_before_update = {
                    str(record_id)
                    for record_id, record in memory_before.get("records", {}).items()
                    if isinstance(record, Mapping)
                    and record.get("status") == "suspected_stale"
                }
                updated_record_ids = self.memory.observe(
                    current_observation,
                    step=step,
                    observation_id=post_observation_id,
                )
                memory_navigation_recovered_ids = (
                    memory_navigation_guard.refresh_visible_records(
                        updated_record_ids
                    )
                )
                recovered_ids = stale_ids_before_update.intersection(updated_record_ids)
                if recovered_ids:
                    stale_record_recovery_count += len(recovered_ids)
                    stale_rediscovery_step = step
                    memory_correction_step = step
                    stale_fallback_active = False

                marked_stale_ids: list[str] = []
                if (
                    config.condition == "stale_r1"
                    and decision.memory_guided
                    and not self._visible_target(
                        current_observation, runtime_spec.retrieval_target_type
                    )
                ):
                    retrieved_by_id = {
                        str(record.get("record_id", "")): record
                        for record in retrieved
                    }
                    marker = getattr(self.memory, "mark_suspected_stale", None)
                    for record_id in decision.memory_record_ids:
                        record = retrieved_by_id.get(record_id)
                        if (
                            record is not None
                            and self._at_last_seen_viewpoint(
                                current_observation, record
                            )
                            and callable(marker)
                            and marker(record_id, step=step)
                        ):
                            marked_stale_ids.append(record_id)
                    if marked_stale_ids:
                        old_viewpoint_miss_count += len(marked_stale_ids)
                        stale_fallback_active = True
                memory_after = self.memory.snapshot()

                evaluator_state = self.env.get_evaluator_state()
                writer.log_evaluator_state(step=step, metadata=evaluator_state)
                success_result = evaluate_task_success(task, evaluator_state)
                success = success_result.success
                ordered_subgoal_passed: bool | None = None
                if config.task == "thor_cup_after_coffee_subgoal":
                    ordered_subgoal_passed = progress.snapshot().get(
                        "ordered_subgoal_passed"
                    )
                    if success and ordered_subgoal_passed is not True:
                        success = False
                        failure_reason = "ordered_subgoal_audit_failed"

                action_history.append(
                    {
                        "step": step,
                        "action": deepcopy(execution.action),
                        "success": execution.success,
                        "error_message": execution.error_message,
                        "reason_code": decision.reason_code,
                    }
                )
                external_call = getattr(self.planner, "last_call", None)
                record = {
                    "trace_schema_version": TRACE_SCHEMA_VERSION,
                    "timestamp": _utc_now(),
                    "step": step,
                    "observation": frame_record,
                    "planner_input": {
                        "request": request.snapshot(),
                        "audit": audit.snapshot(),
                    },
                    "planner_decision": {
                        **decision.snapshot(),
                        "validation_passed": valid_decision,
                        "validation_errors": list(decision_errors),
                        "planning_latency_seconds": planning_latency,
                        "external_call": (
                            to_jsonable(asdict(external_call))
                            if external_call is not None
                            else None
                        ),
                    },
                    "environment_feedback": {
                        "action_success": execution.success,
                        "invalid_action": execution.invalid_action,
                        "error_message": execution.error_message,
                        "post_action_observation": deepcopy(current_observation),
                        "action_latency_seconds": action_latency,
                        "memory_before": memory_before,
                        "memory_update": memory_snapshot_diff(
                            memory_before, memory_after
                        ),
                        "memory_updated_record_ids": updated_record_ids,
                        "memory_marked_stale_record_ids": marked_stale_ids,
                        "memory_recovered_record_ids": sorted(recovered_ids),
                        "memory_navigation_suppressed_record_ids": list(
                            memory_navigation_suppressed_ids
                        ),
                        "memory_navigation_recovered_record_ids": list(
                            memory_navigation_recovered_ids
                        ),
                        "memory_navigation_guard": (
                            memory_navigation_guard.snapshot(
                                include_record_ids=True
                            )
                        ),
                        "memory_after": memory_after,
                        "shared_search_result": (
                            {
                                "route_id": active_route.route_id,
                                "route_kind": active_route_kind,
                                "phase": shared_search.get("phase"),
                                "action_index": shared_search.get("action_index"),
                                "coverage_cursor_after": (
                                    active_route_state.coverage_cursor
                                    if active_route_state is not None
                                    else None
                                ),
                                "action_accepted": execution.success,
                            }
                            if shared_search is not None
                            and active_route is not None
                            else None
                        ),
                        "task_progress": progress.snapshot(),
                        "task_success": success,
                        "evaluator_state_success": success_result.success,
                        "ordered_subgoal_passed": ordered_subgoal_passed,
                        "task_success_channel": (
                            "evaluator-only boolean; not included in the next planner request"
                        ),
                    },
                }
                writer.log_step(record)

                if config.mode == "debug":
                    render_console_step(record)
                if viewer is not None:
                    try:
                        display_result = viewer.show(
                            pre_action_frame, step_delay=config.step_delay
                        )
                    except Exception as exc:
                        display_result = None
                        visualization_failure_reason = (
                            f"viewer_show_error:{type(exc).__name__}:{exc}"
                        )
                        visualization_available = False
                        episode_continued_after_viewer_failure = True
                        print(
                            "Live viewer raised an error; continuing the episode "
                            f"with non-GUI artifacts: {visualization_failure_reason}"
                        )
                    if display_result is not None and display_result.displayed:
                        visualization_displayed_frame_count += 1
                    if display_result is not None and display_result.user_stopped:
                        visualization_user_stopped = True
                        visualization_available = False
                        episode_continued_after_viewer_stop = True
                        print(
                            "Live viewer closed by user; the episode will continue "
                            "and retain non-GUI artifacts."
                        )
                    elif display_result is not None and not display_result.available:
                        visualization_failure_reason = (
                            display_result.failure_reason or "viewer_became_unavailable"
                        )
                        visualization_available = False
                        episode_continued_after_viewer_failure = True
                        print(
                            "Live viewer failed; continuing the episode with "
                            f"non-GUI artifacts: {visualization_failure_reason}"
                        )
                    if (
                        display_result is None
                        or display_result.user_stopped
                        or not display_result.available
                    ):
                        try:
                            viewer.close()
                        except Exception:
                            pass
                        viewer = None

            if not success and not failure_reason:
                failure_reason = "max_steps_exceeded"
        except Exception as exc:
            failure_reason = f"episode_error:{type(exc).__name__}:{exc}"
        finally:
            if viewer is not None:
                try:
                    viewer.close()
                except Exception:
                    pass
            self.env.close()

        elapsed = perf_counter() - episode_started
        progress_snapshot = progress.snapshot()
        hidden_step = progress_snapshot.get(
            "book_hidden_step", progress_snapshot.get("cup_hidden_step")
        )
        reacquired_step = progress_snapshot.get(
            "book_reacquired_step", progress_snapshot.get("cup_reacquired_step")
        )
        target_reacquisition_action_count = (
            int(reacquired_step) - int(hidden_step)
            if isinstance(hidden_step, int)
            and isinstance(reacquired_step, int)
            and reacquired_step >= hidden_step
            else None
        )
        summary = {
            "protocol_version": PHASE4_PROTOCOL_VERSION,
            "episode_id": episode_id,
            "task": config.task,
            "scene": config.scene,
            "planner": config.planner,
            "memory": config.memory,
            "book_distraction_policy": config.book_distraction_policy,
            "condition": config.condition,
            "mode": config.mode,
            "included_in_formal_aggregate": config.included_in_formal_aggregate,
            "run_purpose": config.run_purpose,
            "evidence_status": manifest["evidence_status"],
            "visualization_requested": visualization_requested,
            "visualization_started": visualization_started,
            "visualization_available": visualization_available,
            "visualization_displayed_frame_count": (
                visualization_displayed_frame_count
            ),
            "visualization_failure_reason": visualization_failure_reason,
            "visualization_user_stopped": visualization_user_stopped,
            "episode_continued_after_viewer_failure": (
                episode_continued_after_viewer_failure
            ),
            "episode_continued_after_viewer_stop": (
                episode_continued_after_viewer_stop
            ),
            "visualization_isolated_process": visualization_requested,
            "visualization_diagnostic_log": (
                str(visualization_diagnostic_path)
                if visualization_diagnostic_path is not None
                else None
            ),
            "success": success,
            "failure_reason": "" if success else failure_reason,
            "steps": steps,
            "planner_call_count": planner_call_count,
            "shared_search_route_id": (
                self.search_route.route_id if self.search_route is not None else None
            ),
            "shared_search_action_sequence_digest": (
                self.search_route.action_sequence_digest
                if self.search_route is not None
                else None
            ),
            "shared_search_alignment_action_count": (
                shared_search_alignment_action_count
            ),
            "shared_search_entry_recovery_policy": (
                SHARED_SEARCH_ENTRY_RECOVERY_POLICY_VERSION
            ),
            "shared_search_entry_recovery_action_limit": (
                SHARED_SEARCH_ENTRY_RECOVERY_ACTION_LIMIT
            ),
            "shared_search_entry_departure_action_count": (
                search_route_state.entry_departure_action_count
                if search_route_state is not None
                else 0
            ),
            "shared_search_entry_recovery_action_count": (
                shared_search_entry_recovery_action_count
            ),
            "shared_search_entry_recovery_pending_action_count": (
                search_route_state.entry_recovery_pending_action_count
                if search_route_state is not None
                else 0
            ),
            "shared_search_entry_recovery_record_failure_count": (
                shared_search_entry_recovery_record_failure_count
            ),
            "shared_search_coverage_action_count": (
                shared_search_coverage_action_count
            ),
            "shared_search_route_entry_mismatch_count": (
                shared_search_route_entry_mismatch_count
            ),
            "shared_search_route_exhausted_count": (
                shared_search_route_exhausted_count
            ),
            "shared_search_action_failure_count": (
                shared_search_action_failure_count
            ),
            "shared_subgoal_route_id": (
                self.subgoal_route.route_id if self.subgoal_route is not None else None
            ),
            "shared_subgoal_action_sequence_digest": (
                self.subgoal_route.action_sequence_digest
                if self.subgoal_route is not None
                else None
            ),
            "shared_subgoal_alignment_action_count": shared_subgoal_alignment_action_count,
            "shared_subgoal_coverage_action_count": shared_subgoal_coverage_action_count,
            "shared_subgoal_route_entry_mismatch_count": shared_subgoal_route_entry_mismatch_count,
            "shared_subgoal_route_exhausted_count": shared_subgoal_route_exhausted_count,
            "shared_subgoal_action_failure_count": shared_subgoal_action_failure_count,
            **(
                target_lock_policy.snapshot()
                if target_lock_policy is not None
                else {
                    "target_visible_event_count": 0,
                    "target_lock_entered_count": 0,
                    "target_lock_pickup_attempt_count": 0,
                    "transient_visibility_loss_count": 0,
                    "local_recovery_action_count": 0,
                    "target_reacquired_after_loss_count": 0,
                    "picked_after_target_lock": False,
                    "target_lock_failed_reason": "",
                }
            ),
            "setup_completed": setup_completed,
            "setup_failure_reason": setup_failure_reason,
            "setup_action_count": setup_action_count,
            "average_setup_action_latency_seconds": self._average(
                setup_action_latencies
            ),
            "setup_included_in_planner_metrics": False,
            "memory_guided_action_count": memory_guided_action_count,
            "memory_retrieval_count": memory_retrieval_count,
            "useful_memory_retrieval_count": useful_memory_retrieval_count,
            "short_memory_evicted_before_reacquisition": (
                short_memory_evicted_before_reacquisition
            ),
            "target_reacquisition_action_count": target_reacquisition_action_count,
            "translation_action_count": translation_action_count,
            "translation_distance_meters": translation_distance_meters,
            "search_rotation_count": search_rotation_count,
            "repeated_viewpoint_visit_count": repeated_viewpoint_visit_count,
            "failed_interaction_count": failed_interaction_count,
            "failure_taxonomy": dict(sorted(failure_taxonomy.items())),
            "stale_memory_use_count": stale_memory_use_count,
            "old_viewpoint_miss_count": old_viewpoint_miss_count,
            "stale_record_recovery_count": stale_record_recovery_count,
            "fallback_action_count_after_stale_miss": (
                fallback_action_count_after_stale_miss
            ),
            "stale_rediscovery_step": stale_rediscovery_step,
            "memory_correction_step": memory_correction_step,
            "memory_navigation": memory_navigation_guard.snapshot(),
            "intervention_count": intervention_count,
            "intervention_failure_count": intervention_failure_count,
            "intervention_id": (
                self.intervention.intervention_id
                if self.intervention is not None
                else None
            ),
            "invalid_action_count": invalid_action_count,
            "information_boundary_passed": information_boundary_passed,
            "task_progress": progress_snapshot,
            "average_planning_latency_seconds": self._average(planning_latencies),
            "average_action_latency_seconds": self._average(action_latencies),
            "total_planning_latency_seconds": sum(planning_latencies),
            "total_action_latency_seconds": sum(action_latencies),
            "total_artifact_capture_latency_seconds": sum(artifact_latencies),
            "total_episode_latency_seconds": elapsed,
            "performance_note": (
                "planner, action, and artifact timings are separate; debug delay is not planner latency"
            ),
            "rgb_consumed_by_planner": False,
            "evaluator_debug_saved": config.save_evaluator_debug,
            "evidence_level": "E2",
            "claim": (
                "controlled real-THOR closed-loop and information-flow evidence; "
                "not a memory-improvement result"
            ),
            "manifest": str(writer.manifest_path),
            "setup_log": str(writer.setup_path),
            "evaluator_setup_log": (
                str(writer.private_setup_path)
                if self.evaluator_setup is not None
                else None
            ),
            "episode_log": str(writer.episode_path),
            "summary": str(writer.summary_path),
            "frames_dir": str(writer.frames_dir) if config.save_frames else None,
            "trace_html": str(writer.html_path) if config.trace_html else None,
            "evaluator_debug": (
                str(writer.evaluator_path) if config.save_evaluator_debug else None
            ),
            "intervention_log": (
                str(writer.intervention_path)
                if self.intervention is not None
                else None
            ),
            "finished_at": _utc_now(),
        }
        writer.write_summary(summary)
        if config.trace_html:
            writer.render_html(summary)
        return summary

    def _run_task_setup(
        self,
        writer: ThorTraceWriter,
        runtime_spec: _TaskRuntimeSpec,
        *,
        initial_observation: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool, str, int, list[float]]:
        """Establish the frozen initial view without planner or hidden-state access."""

        observation = (
            deepcopy(dict(initial_observation))
            if initial_observation is not None
            else build_planner_observation(self.env.get_observation())
        )
        frame_record, _ = self._capture_observation_frame(
            writer,
            file_stem="setup_000_reset",
            capture_timing="post_reset",
        )
        writer.log_setup(
            self._setup_record(
                setup_index=0,
                action=None,
                action_success=True,
                error_message="",
                observation=observation,
                frame_record=frame_record,
                action_latency=0.0,
                initial_target_type=runtime_spec.initial_target_type,
            )
        )
        if self._has_visible_pickupable_target(
            observation, runtime_spec.initial_target_type
        ):
            return observation, True, "", 0, []

        latencies: list[float] = []
        action_count = 0
        for setup_index, action in enumerate(runtime_spec.setup_actions, start=1):
            started = perf_counter()
            execution = self.executor.execute(self.env, action)
            action_latency = perf_counter() - started
            latencies.append(action_latency)
            action_count += 1
            observation = build_planner_observation(self.env.get_observation())
            frame_record, _ = self._capture_observation_frame(
                writer,
                file_stem=f"setup_{setup_index:03d}_observation",
                capture_timing="post_setup_action",
            )
            writer.log_setup(
                self._setup_record(
                    setup_index=setup_index,
                    action=execution.action,
                    action_success=execution.success,
                    error_message=execution.error_message,
                    observation=observation,
                    frame_record=frame_record,
                    action_latency=action_latency,
                    initial_target_type=runtime_spec.initial_target_type,
                )
            )
            if execution.invalid_action or not execution.success:
                reason = (
                    f"setup_action_failed:{action.get('action', '')}:"
                    f"{execution.error_message}"
                )
                return observation, False, reason, action_count, latencies
            if self._has_visible_pickupable_target(
                observation, runtime_spec.initial_target_type
            ):
                return observation, True, "", action_count, latencies

        missing_reason = (
            "setup_visible_pickupable_book_missing_after_frozen_sequence"
            if runtime_spec.initial_target_type == "Book"
            else (
                "setup_visible_pickupable_target_missing_after_frozen_sequence:"
                f"{runtime_spec.initial_target_type}"
            )
        )
        return (
            observation,
            False,
            missing_reason,
            action_count,
            latencies,
        )

    @staticmethod
    def _has_visible_pickupable_target(
        observation: Mapping[str, Any], object_type: str
    ) -> bool:
        objects = observation.get("objects", [])
        if not isinstance(objects, list):
            return False
        return any(
            isinstance(obj, Mapping)
            and obj.get("visible") is True
            and str(obj.get("objectType", "")) == object_type
            and bool(obj.get("pickupable", False))
            for obj in objects
        )

    @staticmethod
    def _has_visible_pickupable_book(observation: Mapping[str, Any]) -> bool:
        """Backward-compatible Phase 4 setup predicate."""

        return ThorEpisodeRunner._has_visible_pickupable_target(observation, "Book")

    @staticmethod
    def _visible_target(observation: Mapping[str, Any], object_type: str) -> bool:
        objects = observation.get("objects", [])
        return isinstance(objects, list) and any(
            isinstance(obj, Mapping)
            and obj.get("visible") is True
            and str(obj.get("objectType", "")) == object_type
            for obj in objects
        )

    @staticmethod
    def _at_last_seen_viewpoint(
        observation: Mapping[str, Any], record: Mapping[str, Any]
    ) -> bool:
        """Use visible-history pose only to decide whether negative evidence is sufficient."""

        agent = observation.get("agent", {})
        if not isinstance(agent, Mapping):
            return False
        current_position = agent.get("position")
        remembered_position = record.get("last_seen_agent_position")
        current_rotation = agent.get("rotation")
        remembered_rotation = record.get("last_seen_agent_rotation")
        if not all(
            isinstance(value, Mapping)
            for value in (
                current_position,
                remembered_position,
                current_rotation,
                remembered_rotation,
            )
        ):
            return False

        def number(value: Mapping[str, Any], key: str) -> float:
            raw = value.get(key, 0.0)
            return float(raw) if isinstance(raw, (int, float)) else 0.0

        dx = number(current_position, "x") - number(remembered_position, "x")
        dz = number(current_position, "z") - number(remembered_position, "z")
        if math.hypot(dx, dz) > 0.18:
            return False
        yaw_delta = (
            number(remembered_rotation, "y")
            - number(current_rotation, "y")
            + 180.0
        ) % 360.0 - 180.0
        if abs(yaw_delta) > 1.0:
            return False
        remembered_horizon = record.get("last_seen_camera_horizon")
        current_horizon = agent.get("cameraHorizon")
        if isinstance(remembered_horizon, (int, float)) and isinstance(
            current_horizon, (int, float)
        ):
            if abs(float(remembered_horizon) - float(current_horizon)) > 1.0:
                return False
        return True

    @staticmethod
    def _setup_record(
        *,
        setup_index: int,
        action: Mapping[str, Any] | None,
        action_success: bool,
        error_message: str,
        observation: Mapping[str, Any],
        frame_record: Mapping[str, Any],
        action_latency: float,
        initial_target_type: str = "Book",
    ) -> dict[str, Any]:
        visible_ids = list(visible_object_ids(observation))
        return {
            "trace_schema_version": TRACE_SCHEMA_VERSION,
            "timestamp": _utc_now(),
            "phase": "planner_independent_task_setup",
            "setup_index": setup_index,
            "action": deepcopy(action) if action is not None else None,
            "action_success": action_success,
            "error_message": error_message,
            "action_latency_seconds": action_latency,
            "planner_called": False,
            "uses_evaluator_metadata": False,
            "included_in_planner_metrics": False,
            "planner_safe_observation": deepcopy(observation),
            "planner_safe_observation_digest": stable_digest(observation),
            "visible_object_ids": visible_ids,
            "visible_pickupable_book": ThorEpisodeRunner._has_visible_pickupable_book(
                observation
            ),
            "initial_target_type": initial_target_type,
            "visible_pickupable_target": (
                ThorEpisodeRunner._has_visible_pickupable_target(
                    observation, initial_target_type
                )
            ),
            "rgb_observation": deepcopy(frame_record),
        }

    def _capture_pre_action_frame(
        self, writer: ThorTraceWriter, *, step: int
    ) -> tuple[dict[str, Any], Any]:
        return self._capture_observation_frame(
            writer,
            file_stem=f"step_{step:03d}_observation",
            capture_timing="pre_action",
        )

    def _capture_observation_frame(
        self,
        writer: ThorTraceWriter,
        *,
        file_stem: str,
        capture_timing: str,
    ) -> tuple[dict[str, Any], Any]:
        event = getattr(self.env, "last_event", None)
        frame = getattr(event, "frame", None)
        diagnostics = rgb_array_diagnostics(frame)
        relative_path: str | None = None
        frame_hash: str | None = None
        if self.config.save_frames:
            writer.frames_dir.mkdir(parents=True, exist_ok=True)
            path = self.env.save_frame(writer.frames_dir / f"{file_stem}.png")
            relative_path = path.relative_to(writer.output_dir).as_posix()
            frame_hash = file_sha256(path)
        return (
            {
                "frame_path": relative_path,
                "frame_sha256": frame_hash,
                "rgb_array_diagnostics": diagnostics,
                "capture_timing": capture_timing,
                "desktop_screenshot_used": False,
                "rgb_consumed_by_planner": False,
                "boundary_label": RGB_BOUNDARY_LABEL,
            },
            frame,
        )

    @staticmethod
    def _audit_with_provenance(
        audit: PlannerInputAudit,
        request: PlannerRequest,
        visible_history: Mapping[str, set[str]],
    ) -> PlannerInputAudit:
        violations = list(audit.violations)
        for index, record in enumerate(request.retrieved_memory):
            source = str(record.get("source_observation_id", ""))
            object_id = str(record.get("object_id", ""))
            if source not in visible_history:
                violations.append(f"memory_source_not_in_visible_history:{index}")
            elif object_id not in visible_history[source]:
                violations.append(f"memory_object_not_visible_at_source:{index}")
        return PlannerInputAudit(
            passed=not violations,
            violations=tuple(violations),
            visible_object_ids=audit.visible_object_ids,
            memory_record_ids=audit.memory_record_ids,
            input_digest=audit.input_digest,
        )

    @staticmethod
    def _average(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _viewpoint_key(
        observation: Mapping[str, Any],
    ) -> tuple[float, ...] | None:
        agent = observation.get("agent", {})
        if not isinstance(agent, Mapping):
            return None
        position = agent.get("position", {})
        rotation = agent.get("rotation", {})
        if not isinstance(position, Mapping) or not isinstance(rotation, Mapping):
            return None
        try:
            return (
                round(float(position["x"]), 2),
                round(float(position["z"]), 2),
                round(float(rotation.get("y", 0.0)) % 360.0, 1),
                round(float(agent.get("cameraHorizon", 0.0)), 1),
            )
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _translation_distance(
        before: Mapping[str, Any], after: Mapping[str, Any]
    ) -> float | None:
        before_agent = before.get("agent", {})
        after_agent = after.get("agent", {})
        if not isinstance(before_agent, Mapping) or not isinstance(after_agent, Mapping):
            return None
        before_position = before_agent.get("position", {})
        after_position = after_agent.get("position", {})
        if not isinstance(before_position, Mapping) or not isinstance(after_position, Mapping):
            return None
        try:
            return math.hypot(
                float(after_position["x"]) - float(before_position["x"]),
                float(after_position["z"]) - float(before_position["z"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

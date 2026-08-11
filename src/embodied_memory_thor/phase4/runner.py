"""One real-THOR episode engine shared by formal and debug presentations."""

from __future__ import annotations

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
    StructuredPlanner,
    build_structured_planner,
    validate_planner_decision,
)
from embodied_memory_thor.phase4.spatial_memory import (
    ThorMemoryProvider,
    build_thor_memory,
)
from embodied_memory_thor.phase4.task import BookReacquireProgress
from embodied_memory_thor.phase4.trace import (
    LiveFrameViewer,
    ThorTraceWriter,
    file_sha256,
    render_console_step,
    rgb_array_diagnostics,
)
from embodied_memory_thor.utils.serialization import to_jsonable


PHASE4_PROTOCOL_VERSION = "phase4-v3"
PHASE4_TASKS_PATH = Path(__file__).resolve().parents[3] / "configs" / "phase4_tasks.yaml"
SUPPORTED_BOOK_TASKS = {"thor_book_reacquire", "thor_book_reacquire_k2"}
THOR_BOOK_SETUP_ACTIONS: tuple[dict[str, str], ...] = (
    {"action": "RotateRight"},
    {"action": "MoveAhead"},
    {"action": "RotateRight"},
)


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
    mode: str = "formal"
    max_steps: int = 12
    output_dir: Path | None = None
    save_frames: bool = False
    trace_html: bool = True
    visualize: bool = False
    step_delay: float = 0.0
    save_evaluator_debug: bool = False
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
        if self.task not in SUPPORTED_BOOK_TASKS:
            raise ValueError(f"unsupported real Book task: {self.task}")
        if not self.scene.strip():
            raise ValueError("scene must be non-empty")
        if self.planner not in {"deterministic", "openai_compatible"}:
            raise ValueError(f"unsupported planner: {self.planner}")
        if self.memory not in {"no_memory", "short_memory_k2", "object_memory"}:
            raise ValueError(f"unsupported memory mode: {self.memory}")
        if self.mode not in {"formal", "debug"}:
            raise ValueError("mode must be formal or debug")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.step_delay < 0:
            raise ValueError("step_delay cannot be negative")
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
        viewer_factory: Callable[..., LiveFrameViewer] | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self.env = env or ThorEnv(controller_kwargs=config.controller_settings)
        self.planner = planner or build_structured_planner(
            config.planner, model=config.model, base_url=config.base_url
        )
        self.memory = memory or build_thor_memory(config.memory)
        self.action_space = ActionSpace()
        self.executor = ActionExecutor(self.action_space)
        self.viewer_factory = viewer_factory or LiveFrameViewer

    def run(self) -> dict[str, Any]:
        config = self.config
        task = load_task(config.task, PHASE4_TASKS_PATH)
        output_dir = config.output_dir or default_thor_output_dir(
            task=config.task, planner=config.planner, mode=config.mode
        )
        writer = ThorTraceWriter(
            output_dir, evaluator_debug=config.save_evaluator_debug
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
            "task_setup": {
                "policy": "fixed_planner_independent_visible_observation_sequence",
                "actions": deepcopy(THOR_BOOK_SETUP_ACTIONS),
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
        manifest["evidence_status"] = (
            "formal_acceptance_candidate"
            if manifest["working_tree_dirty"] is False and config.mode == "formal"
            else "development_only"
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

        progress = (
            BookReacquireProgress.phase5_k2()
            if config.task == "thor_book_reacquire_k2"
            else BookReacquireProgress()
        )
        visible_history: dict[str, set[str]] = {}
        action_history: list[dict[str, Any]] = []
        planning_latencies: list[float] = []
        action_latencies: list[float] = []
        artifact_latencies: list[float] = []
        information_boundary_passed = True
        invalid_action_count = 0
        memory_guided_action_count = 0
        planner_call_count = 0
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
            (
                current_observation,
                setup_completed,
                setup_failure_reason,
                setup_action_count,
                setup_action_latencies,
            ) = self._run_task_setup(writer)
            progress.initialize(current_observation)
            visible_history["observation:0"] = set(visible_object_ids(current_observation))
            self.memory.observe(
                current_observation, step=0, observation_id="observation:0"
            )

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
                memory_before = self.memory.snapshot()
                retrieved = tuple(self.memory.retrieve("Book"))
                request = PlannerRequest(
                    task_name=task.task_name,
                    instruction=task.natural_language_instruction,
                    task_stage=progress.stage,
                    step=step,
                    max_steps=config.max_steps,
                    observation=deepcopy(current_observation),
                    allowed_actions=THOR_BOOK_ACTIONS,
                    retrieved_memory=retrieved,
                    recent_action_results=tuple(deepcopy(action_history[-5:])),
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

                action_started = perf_counter()
                execution = self.executor.execute(self.env, decision.action)
                action_latency = perf_counter() - action_started
                action_latencies.append(action_latency)
                if execution.invalid_action:
                    invalid_action_count += 1

                current_observation = build_planner_observation(
                    self.env.get_observation()
                )
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
                updated_record_ids = self.memory.observe(
                    current_observation,
                    step=step,
                    observation_id=post_observation_id,
                )
                memory_after = self.memory.snapshot()

                evaluator_state = self.env.get_evaluator_state()
                writer.log_evaluator_state(step=step, metadata=evaluator_state)
                success_result = evaluate_task_success(task, evaluator_state)
                success = success_result.success

                action_history.append(
                    {
                        "step": step,
                        "action": deepcopy(execution.action),
                        "success": execution.success,
                        "error_message": execution.error_message,
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
                        "memory_after": memory_after,
                        "task_progress": progress.snapshot(),
                        "task_success": success,
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
        summary = {
            "protocol_version": PHASE4_PROTOCOL_VERSION,
            "episode_id": episode_id,
            "task": config.task,
            "scene": config.scene,
            "planner": config.planner,
            "memory": config.memory,
            "mode": config.mode,
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
            "setup_completed": setup_completed,
            "setup_failure_reason": setup_failure_reason,
            "setup_action_count": setup_action_count,
            "average_setup_action_latency_seconds": self._average(
                setup_action_latencies
            ),
            "setup_included_in_planner_metrics": False,
            "memory_guided_action_count": memory_guided_action_count,
            "invalid_action_count": invalid_action_count,
            "information_boundary_passed": information_boundary_passed,
            "task_progress": progress.snapshot(),
            "average_planning_latency_seconds": self._average(planning_latencies),
            "average_action_latency_seconds": self._average(action_latencies),
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
            "episode_log": str(writer.episode_path),
            "summary": str(writer.summary_path),
            "frames_dir": str(writer.frames_dir) if config.save_frames else None,
            "trace_html": str(writer.html_path) if config.trace_html else None,
            "evaluator_debug": (
                str(writer.evaluator_path) if config.save_evaluator_debug else None
            ),
            "finished_at": _utc_now(),
        }
        writer.write_summary(summary)
        if config.trace_html:
            writer.render_html(summary)
        return summary

    def _run_task_setup(
        self, writer: ThorTraceWriter
    ) -> tuple[dict[str, Any], bool, str, int, list[float]]:
        """Establish the frozen initial view without planner or hidden-state access."""

        observation = build_planner_observation(self.env.get_observation())
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
            )
        )
        if self._has_visible_pickupable_book(observation):
            return observation, True, "", 0, []

        latencies: list[float] = []
        action_count = 0
        for setup_index, action in enumerate(THOR_BOOK_SETUP_ACTIONS, start=1):
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
                )
            )
            if execution.invalid_action or not execution.success:
                reason = (
                    f"setup_action_failed:{action.get('action', '')}:"
                    f"{execution.error_message}"
                )
                return observation, False, reason, action_count, latencies
            if self._has_visible_pickupable_book(observation):
                return observation, True, "", action_count, latencies

        return (
            observation,
            False,
            "setup_visible_pickupable_book_missing_after_frozen_sequence",
            action_count,
            latencies,
        )

    @staticmethod
    def _has_visible_pickupable_book(observation: Mapping[str, Any]) -> bool:
        objects = observation.get("objects", [])
        if not isinstance(objects, list):
            return False
        return any(
            isinstance(obj, Mapping)
            and obj.get("visible") is True
            and str(obj.get("objectType", "")) == "Book"
            and bool(obj.get("pickupable", False))
            for obj in objects
        )

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

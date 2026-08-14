"""One intentionally bounded Phase 4 case to run before broader testing."""

from __future__ import annotations

import json
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from embodied_memory_thor.env.base import EmbodiedEnv
from embodied_memory_thor.phase4.contracts import EVALUATOR_CANARY
from embodied_memory_thor.phase4.parity import compare_trace_parity
from embodied_memory_thor.phase4.runner import ThorEpisodeConfig, ThorEpisodeRunner
from embodied_memory_thor.phase4.trace import LiveFrameViewer, ViewerDisplayResult


class _TinyRgbFrame:
    """Small nonblack uint8-like frame used without an image dependency."""

    shape = (2, 2, 3)
    dtype = "uint8"

    @staticmethod
    def tobytes() -> bytes:
        return bytes((0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 255))


class _SingleCaseThorEnv(EmbodiedEnv):
    """Reset-hidden Book reached by fixed setup, then reacquired from memory."""

    def __init__(self) -> None:
        self.yaw = 270
        self.z = 1.0
        self.book_picked = False
        self.last_event = self._event(last_action="Reset", success=True)

    def reset(self, scene: str) -> Any:
        if scene != "FloorPlan1":
            raise ValueError("the single case is frozen to FloorPlan1")
        self.yaw = 270
        self.z = 1.0
        self.book_picked = False
        self.last_event = self._event(last_action="Reset", success=True)
        return self.last_event

    def step(self, action_dict: Mapping[str, Any]) -> Any:
        action = str(action_dict.get("action", ""))
        success = True
        error = ""
        if action == "RotateRight":
            self.yaw = (self.yaw + 90) % 360
        elif action == "RotateLeft":
            self.yaw = (self.yaw - 90) % 360
        elif action == "MoveAhead":
            self.z += 0.25
        elif action == "PickupObject":
            success = (
                action_dict.get("objectId") == "Book|1"
                and self.yaw == 90
                and self.z == 1.25
                and not self.book_picked
            )
            if success:
                self.book_picked = True
            else:
                error = "book is not currently visible and pickupable"
        elif action not in {"LookUp", "LookDown", "Pass"}:
            success = False
            error = f"unsupported fake action: {action}"
        self.last_event = self._event(last_action=action, success=success, error=error)
        return self.last_event

    def get_visible_objects(self) -> list[dict[str, Any]]:
        return [
            deepcopy(obj)
            for obj in self.last_event.metadata["objects"]
            if obj.get("visible")
        ]

    def get_all_objects(self) -> list[dict[str, Any]]:
        return deepcopy(self.last_event.metadata["objects"])

    def get_agent_state(self) -> dict[str, Any]:
        return deepcopy(self.last_event.metadata["agent"])

    def get_observation(self) -> dict[str, Any]:
        metadata = deepcopy(self.last_event.metadata)
        metadata["objects"] = self.get_visible_objects()
        metadata.pop("evaluator_only_secret", None)
        return metadata

    def get_evaluator_state(self) -> dict[str, Any]:
        return deepcopy(self.last_event.metadata)

    def save_frame(self, path: str | Path) -> Path:
        raise AssertionError("the first bounded case deliberately disables frame saving")

    def close(self) -> None:
        return None

    def _event(self, *, last_action: str, success: bool, error: str = "") -> Any:
        book_visible = self.yaw == 90 and self.z == 1.25 and not self.book_picked
        objects = [
            {
                "objectType": "Book",
                "objectId": "Book|1",
                "position": {"x": 0.25, "y": 0.8, "z": 1.0},
                "visible": book_visible,
                "pickupable": True,
                "isPickedUp": self.book_picked,
            },
            {
                "objectType": "Mug",
                "objectId": "Mug|hidden",
                "position": {"x": 9.0, "y": 0.8, "z": 9.0},
                "visible": False,
                "pickupable": True,
            },
        ]
        metadata = {
            "sceneName": "FloorPlan1",
            "agent": {
                "position": {"x": -1.0, "y": 0.9, "z": self.z},
                "rotation": {"x": 0.0, "y": self.yaw, "z": 0.0},
                "cameraHorizon": 0.0,
                "isStanding": True,
            },
            "objects": objects,
            "inventoryObjects": (
                [{"objectId": "Book|1", "objectType": "Book"}]
                if self.book_picked
                else []
            ),
            "lastAction": last_action,
            "lastActionSuccess": success,
            "errorMessage": error,
            "evaluator_only_secret": EVALUATOR_CANARY,
        }
        return SimpleNamespace(metadata=metadata, frame=_TinyRgbFrame())


class _SetupFailureThorEnv(_SingleCaseThorEnv):
    """Fail the frozen setup movement while retaining a valid safe observation."""

    def step(self, action_dict: Mapping[str, Any]) -> Any:
        if str(action_dict.get("action", "")) == "MoveAhead":
            self.last_event = self._event(
                last_action="MoveAhead",
                success=False,
                error="blocked during frozen setup",
            )
            return self.last_event
        return super().step(action_dict)


def _viewer_worker_crashes_after_one_frame(
    frame_queue: Any,
    status_queue: Any,
    title: str,
    stderr_path: str | None,
) -> None:
    """Test worker that proves a native-style process exit remains isolated."""

    del title, stderr_path
    status_queue.put({"kind": "ready"})
    frame_queue.get()
    status_queue.put({"kind": "displayed"})
    frame_queue.get()
    os._exit(17)


class _UnavailableViewer:
    def __init__(self, **kwargs: Any) -> None:
        del kwargs
        self.startup_status = ViewerDisplayResult(
            available=False,
            failure_reason="viewer_startup_error:simulated_xcb_failure",
        )

    def show(self, rgb_frame: Any, *, step_delay: float) -> ViewerDisplayResult:
        raise AssertionError("unavailable viewer must never receive a frame")

    def close(self) -> None:
        return None


class _ViewerFailsAfterOneFrame:
    def __init__(self, **kwargs: Any) -> None:
        del kwargs
        self.startup_status = ViewerDisplayResult(available=True)
        self.calls = 0

    def show(self, rgb_frame: Any, *, step_delay: float) -> ViewerDisplayResult:
        del rgb_frame, step_delay
        self.calls += 1
        if self.calls == 1:
            return ViewerDisplayResult(available=True, displayed=True)
        return ViewerDisplayResult(
            available=False,
            failure_reason="viewer_process_exited_during_display:exit_code=-6",
        )

    def close(self) -> None:
        return None


class Phase4SingleCaseTests(unittest.TestCase):
    def test_floorplan1_book_object_memory_single_case(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            output_dir = Path(temporary_dir) / "single_case"
            config = ThorEpisodeConfig(
                task="thor_book_reacquire",
                scene="FloorPlan1",
                planner="deterministic",
                memory="object_memory",
                mode="formal",
                max_steps=6,
                output_dir=output_dir,
                save_frames=False,
                trace_html=False,
                visualize=False,
                save_evaluator_debug=False,
            )
            summary = ThorEpisodeRunner(config, env=_SingleCaseThorEnv()).run()

            self.assertTrue(summary["success"])
            self.assertEqual(summary["steps"], 3)
            self.assertTrue(summary["setup_completed"])
            self.assertEqual(summary["setup_action_count"], 3)
            self.assertFalse(summary["setup_included_in_planner_metrics"])
            self.assertEqual(summary["memory_guided_action_count"], 1)
            self.assertTrue(summary["information_boundary_passed"])

            records = [
                json.loads(line)
                for line in (output_dir / "episode.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(
                [record["planner_decision"]["action"]["action"] for record in records],
                ["RotateRight", "RotateLeft", "PickupObject"],
            )
            self.assertEqual(
                records[1]["planner_input"]["request"]["retrieved_memory"][0][
                    "source_observation_id"
                ],
                "observation:0",
            )
            episode_text = (output_dir / "episode.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("Mug|hidden", episode_text)
            self.assertNotIn(EVALUATOR_CANARY, episode_text)

            setup_records = [
                json.loads(line)
                for line in (output_dir / "setup.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(len(setup_records), 4)
            self.assertEqual(
                [record["action"]["action"] for record in setup_records[1:]],
                ["RotateRight", "MoveAhead", "RotateRight"],
            )
            self.assertFalse(setup_records[0]["visible_pickupable_book"])
            self.assertTrue(setup_records[-1]["visible_pickupable_book"])
            diagnostics = setup_records[0]["rgb_observation"][
                "rgb_array_diagnostics"
            ]
            self.assertEqual(diagnostics["frame_shape"], [2, 2, 3])
            self.assertFalse(diagnostics["suspected_all_black"])
            self.assertIsNotNone(diagnostics["raw_sha256"])
            self.assertFalse(setup_records[0]["rgb_observation"]["desktop_screenshot_used"])
            self.assertFalse((output_dir / "frames").exists())

    def test_setup_failure_is_auditable_without_planner_or_images(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            output_dir = Path(temporary_dir) / "setup_failure"
            summary = ThorEpisodeRunner(
                ThorEpisodeConfig(
                    output_dir=output_dir,
                    save_frames=False,
                    trace_html=True,
                ),
                env=_SetupFailureThorEnv(),
            ).run()

            self.assertFalse(summary["success"])
            self.assertFalse(summary["setup_completed"])
            self.assertEqual(summary["setup_action_count"], 2)
            self.assertIn("setup_action_failed:MoveAhead", summary["failure_reason"])
            self.assertEqual(summary["planner_call_count"], 0)
            self.assertEqual(summary["steps"], 0)
            self.assertFalse((output_dir / "frames").exists())
            self.assertEqual(
                (output_dir / "episode.jsonl").read_text(encoding="utf-8"), ""
            )
            setup_text = (output_dir / "setup.jsonl").read_text(encoding="utf-8")
            setup_records = [json.loads(line) for line in setup_text.splitlines()]
            self.assertEqual(len(setup_records), 3)
            self.assertFalse(setup_records[-1]["action_success"])
            self.assertEqual(
                setup_records[-1]["error_message"], "blocked during frozen setup"
            )
            self.assertNotIn("Mug|hidden", setup_text)
            self.assertNotIn(EVALUATOR_CANARY, setup_text)
            self.assertTrue((output_dir / "trace.html").is_file())

    def test_formal_and_debug_have_identical_decision_engine_traces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            formal_dir = root / "formal"
            debug_dir = root / "debug"
            shared = {
                "task": "thor_book_reacquire",
                "scene": "FloorPlan1",
                "planner": "deterministic",
                "memory": "object_memory",
                "max_steps": 6,
                "save_frames": False,
                "trace_html": False,
                "visualize": False,
                "save_evaluator_debug": False,
            }
            formal = ThorEpisodeRunner(
                ThorEpisodeConfig(mode="formal", output_dir=formal_dir, **shared),
                env=_SingleCaseThorEnv(),
            ).run()
            with redirect_stdout(io.StringIO()):
                debug = ThorEpisodeRunner(
                    ThorEpisodeConfig(mode="debug", output_dir=debug_dir, **shared),
                    env=_SingleCaseThorEnv(),
                ).run()

            self.assertTrue(formal["success"])
            self.assertTrue(debug["success"])
            parity = compare_trace_parity(
                formal_dir / "episode.jsonl", debug_dir / "episode.jsonl"
            )
            self.assertTrue(parity["passed"], parity["mismatches"])
            self.assertEqual(parity["formal_step_count"], 3)
            self.assertEqual(parity["debug_step_count"], 3)

            def setup_semantics(path: Path) -> list[tuple[Any, ...]]:
                return [
                    (
                        item["setup_index"],
                        item["action"],
                        item["action_success"],
                        item["visible_object_ids"],
                        item["visible_pickupable_book"],
                        item["planner_safe_observation_digest"],
                    )
                    for item in (
                        json.loads(line)
                        for line in path.read_text(encoding="utf-8").splitlines()
                    )
                ]

            self.assertEqual(
                setup_semantics(formal_dir / "setup.jsonl"),
                setup_semantics(debug_dir / "setup.jsonl"),
            )
            self.assertFalse((formal_dir / "frames").exists())
            self.assertFalse((debug_dir / "frames").exists())

    def test_native_viewer_process_death_is_detected_without_parent_abort(self) -> None:
        viewer = LiveFrameViewer(
            worker_target=_viewer_worker_crashes_after_one_frame,
            startup_timeout_seconds=3.0,
            response_grace_seconds=1.0,
        )
        try:
            self.assertTrue(viewer.startup_status.available)
            first = viewer.show(_TinyRgbFrame(), step_delay=0.0)
            self.assertTrue(first.displayed)
            second = viewer.show(_TinyRgbFrame(), step_delay=0.0)
            self.assertFalse(second.available)
            self.assertIn("exit_code=17", second.failure_reason)
        finally:
            viewer.close()

    def test_viewer_startup_failure_does_not_change_episode_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            output_dir = Path(temporary_dir) / "viewer_startup_failure"
            with redirect_stdout(io.StringIO()):
                summary = ThorEpisodeRunner(
                    ThorEpisodeConfig(
                        mode="debug",
                        output_dir=output_dir,
                        save_frames=False,
                        trace_html=True,
                        visualize=True,
                    ),
                    env=_SingleCaseThorEnv(),
                    viewer_factory=_UnavailableViewer,
                ).run()

            self.assertTrue(summary["success"])
            self.assertEqual(summary["steps"], 3)
            self.assertTrue(summary["visualization_requested"])
            self.assertFalse(summary["visualization_started"])
            self.assertFalse(summary["visualization_available"])
            self.assertEqual(summary["visualization_displayed_frame_count"], 0)
            self.assertIn("simulated_xcb_failure", summary["visualization_failure_reason"])
            self.assertTrue(summary["episode_continued_after_viewer_failure"])
            self.assertFalse((output_dir / "frames").exists())
            self.assertTrue((output_dir / "summary.json").is_file())
            self.assertTrue((output_dir / "trace.html").is_file())

    def test_mid_episode_viewer_failure_preserves_formal_trace_parity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            formal_dir = root / "formal"
            debug_dir = root / "debug_viewer_failure"
            shared = {
                "output_dir": formal_dir,
                "save_frames": False,
                "trace_html": False,
                "max_steps": 6,
            }
            formal = ThorEpisodeRunner(
                ThorEpisodeConfig(mode="formal", visualize=False, **shared),
                env=_SingleCaseThorEnv(),
            ).run()
            with redirect_stdout(io.StringIO()):
                debug = ThorEpisodeRunner(
                    ThorEpisodeConfig(
                        mode="debug",
                        visualize=True,
                        output_dir=debug_dir,
                        save_frames=False,
                        trace_html=False,
                        max_steps=6,
                    ),
                    env=_SingleCaseThorEnv(),
                    viewer_factory=_ViewerFailsAfterOneFrame,
                ).run()

            self.assertTrue(formal["success"])
            self.assertTrue(debug["success"])
            self.assertEqual(debug["steps"], 3)
            self.assertEqual(debug["visualization_displayed_frame_count"], 1)
            self.assertFalse(debug["visualization_available"])
            self.assertTrue(debug["episode_continued_after_viewer_failure"])
            parity = compare_trace_parity(
                formal_dir / "episode.jsonl", debug_dir / "episode.jsonl"
            )
            self.assertTrue(parity["passed"], parity["mismatches"])

    def test_formal_mode_never_constructs_gui_viewer(self) -> None:
        calls: list[dict[str, Any]] = []

        def forbidden_viewer_factory(**kwargs: Any) -> Any:
            calls.append(kwargs)
            raise AssertionError("formal mode must not construct the GUI viewer")

        with tempfile.TemporaryDirectory() as temporary_dir:
            summary = ThorEpisodeRunner(
                ThorEpisodeConfig(
                    mode="formal",
                    visualize=False,
                    output_dir=Path(temporary_dir) / "formal_no_gui",
                    save_frames=False,
                    trace_html=False,
                ),
                env=_SingleCaseThorEnv(),
                viewer_factory=forbidden_viewer_factory,
            ).run()

        self.assertTrue(summary["success"])
        self.assertFalse(summary["visualization_requested"])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()

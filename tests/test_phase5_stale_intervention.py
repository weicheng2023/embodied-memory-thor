"""Offline Phase 5A3 acceptance for evaluator-only stale Book relocation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from embodied_memory_thor.actions import ActionSpace
from embodied_memory_thor.env.base import EmbodiedEnv
from embodied_memory_thor.phase4.contracts import EVALUATOR_CANARY
from embodied_memory_thor.phase4.runner import ThorEpisodeConfig, ThorEpisodeRunner
from tests.test_phase4_single_case import _SingleCaseThorEnv, _TinyRgbFrame


class _RelocatableBookThorEnv(_SingleCaseThorEnv):
    """Book moves from the remembered yaw 90 view to a hidden yaw 0 view."""

    def __init__(self) -> None:
        self.book_yaw = 90
        super().__init__()

    def reset(self, scene: str) -> Any:
        self.book_yaw = 90
        return super().reset(scene)

    def relocate_book_for_evaluator(self, *, destination_yaw: int) -> dict[str, Any]:
        before = self.book_yaw
        self.book_yaw = int(destination_yaw) % 360
        self.last_event = self._event(
            last_action="PlaceObjectAtPoint", success=True
        )
        return {
            "native_action": "PlaceObjectAtPoint",
            "target_object_id": "Book|1",
            "before_yaw": before,
            "destination_yaw": self.book_yaw,
            "success": True,
        }

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
                and self.yaw == self.book_yaw
                and self.z == 1.25
                and not self.book_picked
            )
            if success:
                self.book_picked = True
            else:
                error = "Book is not currently visible and pickupable"
        elif action not in {"LookUp", "LookDown", "Pass"}:
            success = False
            error = f"unsupported stale-task fixture action: {action}"
        self.last_event = self._event(last_action=action, success=success, error=error)
        return self.last_event

    def _event(self, *, last_action: str, success: bool, error: str = "") -> Any:
        book_visible = (
            self.yaw == self.book_yaw
            and self.z == 1.25
            and not self.book_picked
        )
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


class _FrozenBookRelocation:
    intervention_id = "phase5_offline_book_relocation_yaw0"

    def __init__(self) -> None:
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
        if not (
            task_name == "thor_book_reacquire_k2"
            and task_stage == "controlled_distraction_3"
            and step == 3
            and agent_action_success
            and agent_action.get("action") == "LookUp"
        ):
            return None
        visible_types = {
            str(obj.get("objectType", ""))
            for obj in pre_intervention_observation.get("objects", [])
            if isinstance(obj, Mapping) and obj.get("visible") is True
        }
        if "Book" in visible_types:
            raise RuntimeError("frozen stale intervention requires hidden Book")
        if not isinstance(env, _RelocatableBookThorEnv):
            raise TypeError("offline relocation requires the relocatable fixture")
        native = env.relocate_book_for_evaluator(destination_yaw=0)
        self.applied = True
        return {
            "intervention_id": self.intervention_id,
            "task": task_name,
            "trigger_step": step,
            "trigger_stage": task_stage,
            "included_in_planner_metrics": False,
            "planner_visible": False,
            **native,
        }


class _FailedBookRelocation:
    intervention_id = "phase5_offline_failed_relocation"

    def maybe_apply(self, **kwargs: Any) -> Mapping[str, Any] | None:
        if kwargs.get("task_stage") != "controlled_distraction_3":
            return None
        return {
            "intervention_id": self.intervention_id,
            "success": False,
            "private_error": "simulated invalid destination",
        }


class Phase5StaleInterventionTests(unittest.TestCase):
    def test_matched_relocation_is_private_and_object_memory_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            summaries = {}
            traces = {}
            intervention_records = {}
            for variant in ("no_memory", "short_memory_k2", "object_memory"):
                output_dir = root / variant
                summaries[variant] = ThorEpisodeRunner(
                    ThorEpisodeConfig(
                        task="thor_book_reacquire_k2",
                        memory=variant,
                        condition="stale_r1",
                        mode="formal",
                        max_steps=12,
                        output_dir=output_dir,
                        save_frames=False,
                        trace_html=False,
                        visualize=False,
                    ),
                    env=_RelocatableBookThorEnv(),
                    intervention=_FrozenBookRelocation(),
                ).run()
                traces[variant] = self._jsonl(output_dir / "episode.jsonl")
                intervention_records[variant] = self._jsonl(
                    output_dir / "intervention.jsonl"
                )

        for variant, summary in summaries.items():
            self.assertTrue(summary["success"], variant)
            self.assertEqual(summary["condition"], "stale_r1")
            self.assertTrue(summary["information_boundary_passed"], variant)
            self.assertEqual(summary["intervention_count"], 1)
            self.assertEqual(len(intervention_records[variant]), 1)
            private = intervention_records[variant][0]
            self.assertEqual(private["destination_yaw"], 0)
            self.assertEqual(private["native_action"], "PlaceObjectAtPoint")
            episode_text = json.dumps(traces[variant])
            self.assertNotIn("PlaceObjectAtPoint", episode_text)
            self.assertNotIn("destination_yaw", episode_text)
            self.assertNotIn(_FrozenBookRelocation.intervention_id, episode_text)
            self.assertNotIn(EVALUATOR_CANARY, episode_text)
            step3_after = traces[variant][2]["environment_feedback"][
                "post_action_observation"
            ]
            self.assertEqual(step3_after["last_action"], "LookUp")

        for variant in ("no_memory", "short_memory_k2"):
            summary = summaries[variant]
            self.assertEqual(summary["stale_memory_use_count"], 0)
            self.assertEqual(summary["old_viewpoint_miss_count"], 0)
            self.assertEqual(summary["stale_record_recovery_count"], 0)

        object_summary = summaries["object_memory"]
        self.assertEqual(object_summary["stale_memory_use_count"], 1)
        self.assertEqual(object_summary["old_viewpoint_miss_count"], 1)
        self.assertEqual(object_summary["fallback_action_count_after_stale_miss"], 3)
        self.assertEqual(object_summary["stale_record_recovery_count"], 1)
        self.assertEqual(object_summary["stale_rediscovery_step"], 7)
        self.assertEqual(object_summary["memory_correction_step"], 7)
        self.assertEqual(object_summary["steps"], 8)
        self.assertEqual(summaries["no_memory"]["steps"], 6)
        self.assertEqual(summaries["short_memory_k2"]["steps"], 6)

        object_trace = traces["object_memory"]
        miss_feedback = object_trace[3]["environment_feedback"]
        self.assertEqual(
            miss_feedback["memory_marked_stale_record_ids"], ["object:Book|1"]
        )
        self.assertEqual(
            miss_feedback["memory_after"]["records"]["object:Book|1"]["status"],
            "suspected_stale",
        )
        self.assertEqual(
            object_trace[4]["planner_input"]["request"]["retrieved_memory"], []
        )
        recovery = object_trace[6]["environment_feedback"]
        self.assertEqual(recovery["memory_recovered_record_ids"], ["object:Book|1"])
        self.assertEqual(
            recovery["memory_after"]["records"]["object:Book|1"]["status"],
            "fresh",
        )
        self.assertEqual(
            recovery["memory_after"]["records"]["object:Book|1"][
                "source_observation_id"
            ],
            "observation:7",
        )

    def test_stale_condition_requires_explicit_intervention(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires an evaluator intervention"):
            ThorEpisodeRunner(
                ThorEpisodeConfig(
                    task="thor_book_reacquire_k2",
                    condition="stale_r1",
                ),
                env=_RelocatableBookThorEnv(),
            )

    def test_native_relocation_is_not_in_agent_action_space(self) -> None:
        self.assertNotIn("PlaceObjectAtPoint", ActionSpace().allowed_actions)

    def test_failed_intervention_stops_episode_with_private_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            output_dir = Path(temporary_dir) / "failed_intervention"
            summary = ThorEpisodeRunner(
                ThorEpisodeConfig(
                    task="thor_book_reacquire_k2",
                    memory="object_memory",
                    condition="stale_r1",
                    output_dir=output_dir,
                    save_frames=False,
                    trace_html=False,
                ),
                env=_RelocatableBookThorEnv(),
                intervention=_FailedBookRelocation(),
            ).run()

            self.assertFalse(summary["success"])
            self.assertEqual(summary["failure_reason"], "evaluator_intervention_failed")
            self.assertEqual(summary["intervention_count"], 1)
            self.assertEqual(summary["intervention_failure_count"], 1)
            self.assertNotIn(
                "simulated invalid destination",
                (output_dir / "episode.jsonl").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "simulated invalid destination",
                (output_dir / "intervention.jsonl").read_text(encoding="utf-8"),
            )

    @staticmethod
    def _jsonl(path: Path) -> list[dict[str, Any]]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
        ]


if __name__ == "__main__":
    unittest.main()

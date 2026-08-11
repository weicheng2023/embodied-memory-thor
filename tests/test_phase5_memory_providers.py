"""Phase 5A1 tests for the real-THOR memory-only treatment difference."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from embodied_memory_thor.phase4.contracts import PlannerRequest, audit_planner_request
from embodied_memory_thor.phase4.planners import ThorBookReacquirePlanner
from embodied_memory_thor.phase4.runner import ThorEpisodeConfig, ThorEpisodeRunner
from embodied_memory_thor.phase4.spatial_memory import build_thor_memory
from embodied_memory_thor.phase4.task import BookReacquireProgress
from embodied_memory_thor.phase5.protocol import PHASE5_REQUIRED_METRICS
from tests.test_phase4_single_case import _SingleCaseThorEnv


def _observation(*, book_visible: bool, yaw: float, marker: str) -> dict:
    objects = [
        {
            "objectType": "CounterTop",
            "objectId": f"CounterTop|{marker}",
            "position": {"x": 0.0, "y": 1.0, "z": 0.0},
            "visible": True,
        }
    ]
    if book_visible:
        objects.append(
            {
                "objectType": "Book",
                "objectId": "Book|1",
                "position": {"x": 0.25, "y": 0.8, "z": 1.0},
                "visible": True,
                "pickupable": True,
            }
        )
    return {
        "scene_name": "FloorPlan1",
        "agent": {
            "position": {"x": 0.0, "y": 0.9, "z": 0.0},
            "rotation": {"x": 0.0, "y": yaw, "z": 0.0},
            "cameraHorizon": 0.0,
            "isStanding": True,
        },
        "objects": objects,
        "inventory": [],
        "last_action": "Pass",
        "last_action_success": True,
        "last_action_error": "",
    }


class Phase5MemoryProviderTests(unittest.TestCase):
    def test_exact_k2_evicts_initial_book_after_two_new_observations(self) -> None:
        memory = build_thor_memory("short_memory_k2")
        initial = _observation(book_visible=True, yaw=0.0, marker="initial")
        memory.observe(initial, step=0, observation_id="observation:0")

        first_hidden = _observation(book_visible=False, yaw=90.0, marker="one")
        memory.observe(first_hidden, step=1, observation_id="observation:1")
        retained = memory.retrieve("Book")
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0]["source_observation_id"], "observation:0")

        second_hidden = _observation(book_visible=False, yaw=180.0, marker="two")
        memory.observe(second_hidden, step=2, observation_id="observation:2")
        self.assertEqual(memory.retrieve("Book"), [])
        self.assertEqual(
            memory.snapshot()["observation_ids"],
            ["observation:1", "observation:2"],
        )

    def test_object_memory_persists_while_no_memory_never_retrieves(self) -> None:
        initial = _observation(book_visible=True, yaw=0.0, marker="initial")
        hidden = _observation(book_visible=False, yaw=90.0, marker="hidden")
        providers = {
            name: build_thor_memory(name)
            for name in ("no_memory", "object_memory")
        }
        for provider in providers.values():
            provider.observe(initial, step=0, observation_id="observation:0")
            provider.observe(hidden, step=1, observation_id="observation:1")
            provider.observe(hidden, step=2, observation_id="observation:2")

        self.assertEqual(providers["no_memory"].retrieve("Book"), [])
        persistent = providers["object_memory"].retrieve("Book")
        self.assertEqual(len(persistent), 1)
        self.assertEqual(persistent[0]["source_observation_id"], "observation:0")
        self.assertTrue(audit_planner_request(self._request(hidden, persistent)).passed)

    def test_no_memory_and_evicted_short_memory_share_fallback_action(self) -> None:
        hidden = _observation(book_visible=False, yaw=180.0, marker="hidden")
        short = build_thor_memory("short_memory_k2")
        short.observe(
            _observation(book_visible=True, yaw=0.0, marker="initial"),
            step=0,
            observation_id="observation:0",
        )
        short.observe(hidden, step=1, observation_id="observation:1")
        short.observe(hidden, step=2, observation_id="observation:2")

        planner = ThorBookReacquirePlanner()
        no_decision = planner.plan(self._request(hidden, []))
        short_decision = planner.plan(self._request(hidden, short.retrieve("Book")))
        self.assertEqual(no_decision.action, short_decision.action)
        self.assertEqual(no_decision.reason_code, "systematic_search")
        self.assertEqual(short_decision.reason_code, "systematic_search")
        self.assertFalse(no_decision.memory_guided)
        self.assertFalse(short_decision.memory_guided)

    def test_active_short_and_object_memory_use_same_record_schema_and_action(self) -> None:
        initial = _observation(book_visible=True, yaw=0.0, marker="initial")
        hidden = _observation(book_visible=False, yaw=90.0, marker="hidden")
        planner = ThorBookReacquirePlanner()
        decisions = {}
        record_key_sets = {}
        for name in ("short_memory_k2", "object_memory"):
            memory = build_thor_memory(name)
            memory.observe(initial, step=0, observation_id="observation:0")
            memory.observe(hidden, step=1, observation_id="observation:1")
            records = memory.retrieve("Book")
            self.assertEqual(len(records), 1)
            record_key_sets[name] = set(records[0])
            decisions[name] = planner.plan(self._request(hidden, records))

        self.assertEqual(
            record_key_sets["short_memory_k2"], record_key_sets["object_memory"]
        )
        self.assertEqual(
            decisions["short_memory_k2"].action,
            decisions["object_memory"].action,
        )
        self.assertEqual(
            decisions["short_memory_k2"].reason_code,
            decisions["object_memory"].reason_code,
        )
        self.assertTrue(decisions["short_memory_k2"].memory_guided)
        self.assertTrue(decisions["object_memory"].memory_guided)

    def test_phase4_runner_contract_accepts_exact_phase5_variant_name(self) -> None:
        ThorEpisodeConfig(memory="short_memory_k2").validate()

    def test_phase4_distraction_retry_semantics_remain_unchanged(self) -> None:
        progress = BookReacquireProgress()
        visible = _observation(book_visible=True, yaw=0.0, marker="visible")
        progress.initialize(visible)
        progress.observe_action(
            step=1,
            action={"action": "RotateRight"},
            success=False,
            observation_after=visible,
        )
        self.assertEqual(progress.stage, "controlled_distraction")
        self.assertEqual(progress.snapshot()["distraction_error"], "")

    def test_phase5_r1_evicts_k2_and_preserves_shared_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            summaries = {}
            traces = {}
            for variant in ("no_memory", "short_memory_k2", "object_memory"):
                output_dir = root / variant
                summaries[variant] = ThorEpisodeRunner(
                    ThorEpisodeConfig(
                        task="thor_book_reacquire_k2",
                        memory=variant,
                        mode="formal",
                        max_steps=10,
                        output_dir=output_dir,
                        save_frames=False,
                        trace_html=False,
                        visualize=False,
                    ),
                    env=_SingleCaseThorEnv(),
                ).run()
                traces[variant] = [
                    json.loads(line)
                    for line in (output_dir / "episode.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                ]

        for summary in summaries.values():
            self.assertTrue(summary["success"])
            self.assertTrue(summary["information_boundary_passed"])
            self.assertTrue(
                set(PHASE5_REQUIRED_METRICS).issubset(summary),
                set(PHASE5_REQUIRED_METRICS).difference(summary),
            )
            self.assertEqual(
                summary["task_progress"]["distraction_transition_count"], 3
            )
            self.assertTrue(
                summary["task_progress"]["short_memory_k2_eviction_ready"]
            )

        expected_distraction = ["RotateRight", "LookDown", "LookUp"]
        for trace in traces.values():
            self.assertEqual(
                [item["planner_decision"]["action"]["action"] for item in trace[:3]],
                expected_distraction,
            )
            self.assertTrue(
                all(
                    not any(
                        obj["objectType"] == "Book"
                        for obj in item["environment_feedback"][
                            "post_action_observation"
                        ]["objects"]
                    )
                    for item in trace[:3]
                )
            )

        no_step4 = traces["no_memory"][3]
        short_step4 = traces["short_memory_k2"][3]
        object_step4 = traces["object_memory"][3]
        self.assertEqual(
            short_step4["planner_input"]["request"]["retrieved_memory"], []
        )
        self.assertEqual(
            no_step4["planner_decision"]["action"],
            short_step4["planner_decision"]["action"],
        )
        self.assertEqual(
            no_step4["planner_decision"]["reason_code"], "systematic_search"
        )
        self.assertEqual(
            short_step4["planner_decision"]["reason_code"], "systematic_search"
        )
        self.assertEqual(
            object_step4["planner_input"]["request"]["retrieved_memory"][0][
                "source_observation_id"
            ],
            "observation:0",
        )
        self.assertTrue(object_step4["planner_decision"]["memory_guided"])
        self.assertEqual(summaries["object_memory"]["steps"], 5)
        self.assertEqual(summaries["no_memory"]["steps"], 7)
        self.assertEqual(summaries["short_memory_k2"]["steps"], 7)
        self.assertEqual(
            summaries["object_memory"]["target_reacquisition_action_count"], 3
        )
        self.assertEqual(
            summaries["no_memory"]["target_reacquisition_action_count"], 5
        )
        self.assertEqual(
            summaries["short_memory_k2"]["target_reacquisition_action_count"], 5
        )
        self.assertFalse(
            summaries["no_memory"]["short_memory_evicted_before_reacquisition"]
        )
        self.assertTrue(
            summaries["short_memory_k2"][
                "short_memory_evicted_before_reacquisition"
            ]
        )
        self.assertFalse(
            summaries["object_memory"][
                "short_memory_evicted_before_reacquisition"
            ]
        )
        self.assertEqual(summaries["no_memory"]["memory_retrieval_count"], 0)
        self.assertGreater(
            summaries["object_memory"]["memory_retrieval_count"], 0
        )
        self.assertEqual(
            summaries["object_memory"]["useful_memory_retrieval_count"],
            summaries["object_memory"]["memory_guided_action_count"],
        )

    @staticmethod
    def _request(observation: dict, records: list[dict]) -> PlannerRequest:
        return PlannerRequest(
            task_name="thor_book_reacquire",
            instruction="Reacquire and pick up the Book.",
            task_stage="reacquire_book",
            step=3,
            max_steps=12,
            observation=observation,
            allowed_actions=(
                "LookDown",
                "LookUp",
                "MoveAhead",
                "Pass",
                "PickupObject",
                "RotateLeft",
                "RotateRight",
            ),
            retrieved_memory=tuple(records),
        )


if __name__ == "__main__":
    unittest.main()

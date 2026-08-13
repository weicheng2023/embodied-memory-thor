"""Offline Phase 5A2 acceptance for the ordered Cup/CoffeeMachine task."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from embodied_memory_thor.phase4.contracts import EVALUATOR_CANARY, PlannerRequest
from embodied_memory_thor.phase4.planners import (
    THOR_CUP_COFFEE_ACTIONS,
    ThorBookReacquirePlanner,
)
from embodied_memory_thor.phase4.runner import ThorEpisodeConfig, ThorEpisodeRunner
from embodied_memory_thor.phase4.task import CupAfterCoffeeProgress
from embodied_memory_thor.phase5.search import FrozenSearchRoute
from tests.test_phase4_single_case import _SingleCaseThorEnv, _TinyRgbFrame


class _CupCoffeeThorEnv(_SingleCaseThorEnv):
    """Cup at yaw 0 and CoffeeMachine at yaw 90 with no hidden-state shortcut."""

    def __init__(self, *, cup_visible_at_reset: bool = True) -> None:
        self.cup_visible_at_reset = cup_visible_at_reset
        self.coffee_toggled = False
        self.cup_picked = False
        self.yaw = 0
        self.z = 1.0
        self.last_event = self._event(last_action="Reset", success=True)

    def reset(self, scene: str) -> Any:
        if scene != "FloorPlan1":
            raise ValueError("the ordered-task fixture is frozen to FloorPlan1")
        self.coffee_toggled = False
        self.cup_picked = False
        self.yaw = 0
        self.z = 1.0
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
        elif action == "ToggleObjectOn":
            success = (
                action_dict.get("objectId") == "CoffeeMachine|1"
                and self.yaw == 90
                and not self.coffee_toggled
            )
            if success:
                self.coffee_toggled = True
            else:
                error = "CoffeeMachine is not currently visible and toggleable"
        elif action == "PickupObject":
            success = (
                action_dict.get("objectId") == "Cup|1"
                and self.yaw == 0
                and self.coffee_toggled
                and not self.cup_picked
            )
            if success:
                self.cup_picked = True
            else:
                error = "Cup is not ready for ordered pickup"
        elif action not in {"LookUp", "LookDown", "MoveAhead", "Pass"}:
            success = False
            error = f"unsupported ordered-task fixture action: {action}"
        self.last_event = self._event(last_action=action, success=success, error=error)
        return self.last_event

    def _event(self, *, last_action: str, success: bool, error: str = "") -> Any:
        cup_visible = (
            self.cup_visible_at_reset and self.yaw == 0 and not self.cup_picked
        )
        machine_visible = self.yaw == 90
        objects = [
            {
                "objectType": "Cup",
                "objectId": "Cup|1",
                "position": {"x": 0.0, "y": 0.9, "z": 1.0},
                "visible": cup_visible,
                "pickupable": True,
                "isPickedUp": self.cup_picked,
            },
            {
                "objectType": "CoffeeMachine",
                "objectId": "CoffeeMachine|1",
                "position": {"x": 1.0, "y": 0.9, "z": 0.0},
                "visible": machine_visible,
                "toggleable": True,
                "isToggled": self.coffee_toggled,
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
                "position": {"x": 0.0, "y": 0.9, "z": self.z},
                "rotation": {"x": 0.0, "y": self.yaw, "z": 0.0},
                "cameraHorizon": 0.0,
                "isStanding": True,
            },
            "objects": objects,
            "inventoryObjects": (
                [{"objectId": "Cup|1", "objectType": "Cup"}]
                if self.cup_picked
                else []
            ),
            "lastAction": last_action,
            "lastActionSuccess": success,
            "errorMessage": error,
            "evaluator_only_secret": EVALUATOR_CANARY,
        }
        return SimpleNamespace(metadata=metadata, frame=_TinyRgbFrame())


class Phase5OrderedTaskTests(unittest.TestCase):
    @staticmethod
    def _route(
        route_id: str,
        action_codes: str,
        *,
        role: str,
        qualification_goal_input_used: bool,
    ) -> FrozenSearchRoute:
        action_names = {
            "D": "LookDown",
            "F": "MoveAhead",
            "L": "RotateLeft",
            "R": "RotateRight",
            "U": "LookUp",
        }
        actions = [{"action": action_names[code]} for code in action_codes]
        digest = hashlib.sha256(
            json.dumps(
                actions,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()
        return FrozenSearchRoute(
            route_id=route_id,
            task="thor_cup_after_coffee_subgoal",
            scene="FloorPlan1",
            source_qualification_route_digest="a" * 64,
            action_sequence_digest=digest,
            action_codes=action_codes,
            route_role=role,
            qualification_goal_input_used=qualification_goal_input_used,
            target_or_anchor_input_used=qualification_goal_input_used,
        )

    def test_frozen_r2_routes_are_shared_action_only_and_role_explicit(self) -> None:
        subgoal = self._route(
            "FloorPlan1_R2_subgoal_fixture",
            "R",
            role="task_subgoal_navigation",
            qualification_goal_input_used=True,
        )
        fallback = self._route(
            "FloorPlan1_R2_fallback_fixture",
            "RRR",
            role="target_independent_fallback",
            qualification_goal_input_used=False,
        )
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            summaries = {}
            traces = {}
            manifests = {}
            ordinary_traces = {}
            for variant in ("no_memory", "short_memory_k2", "object_memory"):
                output_dir = root / variant
                summaries[variant] = ThorEpisodeRunner(
                    ThorEpisodeConfig(
                        task="thor_cup_after_coffee_subgoal",
                        memory=variant,
                        subgoal_route_id=subgoal.route_id,
                        search_route_id=fallback.route_id,
                        max_steps=10,
                        output_dir=output_dir,
                        save_frames=False,
                        trace_html=False,
                    ),
                    env=_CupCoffeeThorEnv(),
                    subgoal_route=subgoal,
                    search_route=fallback,
                ).run()
                traces[variant] = self._jsonl(output_dir / "episode.jsonl")
                manifests[variant] = json.loads(
                    (output_dir / "run_manifest.json").read_text(encoding="utf-8")
                )
                ordinary_traces[variant] = (output_dir / "episode.jsonl").read_text(
                    encoding="utf-8"
                )

        for variant, summary in summaries.items():
            self.assertTrue(summary["success"], (variant, summary["failure_reason"]))
            self.assertTrue(summary["information_boundary_passed"])
            self.assertEqual(summary["shared_subgoal_coverage_action_count"], 1)
            self.assertEqual(summary["shared_subgoal_action_failure_count"], 0)
            manifest = manifests[variant]
            self.assertEqual(
                manifest["subgoal_route"]["route_role"],
                "task_subgoal_navigation",
            )
            self.assertTrue(
                manifest["subgoal_route"]["qualification_goal_input_used"]
            )
            self.assertFalse(
                manifest["search_route"]["qualification_goal_input_used"]
            )
            ordinary = ordinary_traces[variant]
            for forbidden in (
                "target_point",
                "destination_pose",
                "reachable_positions",
                "CoffeeMachine|1",
            ):
                if forbidden == "CoffeeMachine|1":
                    continue  # currently visible object IDs are legitimate planner input
                self.assertNotIn(forbidden, ordinary)

        for trace in traces.values():
            first = trace[0]["planner_input"]["request"]["shared_search"]
            self.assertEqual(first["policy"], "frozen_task_subgoal_route")
            self.assertEqual(first["route_role"], "task_subgoal_navigation")
            self.assertEqual(first["action"], {"action": "RotateRight"})

        self.assertEqual(summaries["object_memory"]["steps"], 4)
        self.assertEqual(summaries["no_memory"]["steps"], 6)
        self.assertEqual(summaries["short_memory_k2"]["steps"], 6)
        for variant in ("no_memory", "short_memory_k2"):
            self.assertEqual(
                summaries[variant]["shared_search_coverage_action_count"], 3
            )
        self.assertEqual(
            summaries["object_memory"]["shared_search_coverage_action_count"], 0
        )

    def test_frozen_subgoal_action_overrides_early_machine_visibility(self) -> None:
        route = self._route(
            "FloorPlan1_R2_subgoal_early_visibility_fixture",
            "R",
            role="task_subgoal_navigation",
            qualification_goal_input_used=True,
        )
        observation = {
            "agent": {
                "position": {"x": 0.0, "y": 0.9, "z": 0.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "cameraHorizon": 0.0,
            },
            "objects": [
                {
                    "objectType": "CoffeeMachine",
                    "objectId": "CoffeeMachine|visible_early",
                    "position": {"x": 0.0, "y": 0.9, "z": 1.0},
                    "visible": True,
                    "toggleable": True,
                }
            ],
            "inventory": [],
        }
        directive = {
            "policy": "frozen_task_subgoal_route",
            "route_role": "task_subgoal_navigation",
            "route_id": route.route_id,
            "action_sequence_digest": route.action_sequence_digest,
            "phase": "coverage",
            "action_index": 0,
            "action": {"action": "RotateRight"},
        }
        request = PlannerRequest(
            task_name="thor_cup_after_coffee_subgoal",
            instruction="Toggle CoffeeMachine before Cup pickup.",
            task_stage="toggle_coffee_machine",
            step=1,
            max_steps=10,
            observation=observation,
            allowed_actions=THOR_CUP_COFFEE_ACTIONS,
            shared_search=directive,
        )
        decision = ThorBookReacquirePlanner().plan(request)
        self.assertEqual(decision.action, {"action": "RotateRight"})
        self.assertEqual(decision.reason_code, "shared_subgoal_navigation")

    def test_three_variants_share_ordered_subgoal_and_memory_only_difference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            summaries = {}
            traces = {}
            setup_records = {}
            for variant in ("no_memory", "short_memory_k2", "object_memory"):
                output_dir = root / variant
                summaries[variant] = ThorEpisodeRunner(
                    ThorEpisodeConfig(
                        task="thor_cup_after_coffee_subgoal",
                        memory=variant,
                        mode="formal",
                        max_steps=10,
                        output_dir=output_dir,
                        save_frames=False,
                        trace_html=False,
                        visualize=False,
                    ),
                    env=_CupCoffeeThorEnv(),
                ).run()
                traces[variant] = self._jsonl(output_dir / "episode.jsonl")
                setup_records[variant] = self._jsonl(output_dir / "setup.jsonl")

        for variant, summary in summaries.items():
            self.assertTrue(summary["success"], variant)
            self.assertTrue(summary["information_boundary_passed"], variant)
            self.assertEqual(summary["setup_action_count"], 0)
            progress = summary["task_progress"]
            self.assertEqual(progress["coffee_machine_toggled_step"], 2)
            self.assertLess(
                progress["coffee_machine_toggled_step"], progress["cup_picked_step"]
            )
            self.assertTrue(progress["ordered_subgoal_passed"])
            self.assertEqual(progress["protocol_violations"], [])
            final_feedback = traces[variant][-1]["environment_feedback"]
            self.assertTrue(final_feedback["evaluator_state_success"])
            self.assertTrue(final_feedback["ordered_subgoal_passed"])
            self.assertTrue(final_feedback["task_success"])
            self.assertNotIn("Mug|hidden", json.dumps(traces[variant]))
            self.assertNotIn(EVALUATOR_CANARY, json.dumps(traces[variant]))
            self.assertTrue(setup_records[variant][0]["visible_pickupable_target"])
            self.assertEqual(setup_records[variant][0]["initial_target_type"], "Cup")

        for trace in traces.values():
            self.assertEqual(
                [item["planner_decision"]["action"]["action"] for item in trace[:2]],
                ["RotateRight", "ToggleObjectOn"],
            )
            self.assertFalse(
                any(
                    obj["objectType"] == "Cup"
                    for obj in trace[1]["environment_feedback"][
                        "post_action_observation"
                    ]["objects"]
                )
            )

        no_step3 = traces["no_memory"][2]
        short_step3 = traces["short_memory_k2"][2]
        object_step3 = traces["object_memory"][2]
        self.assertEqual(
            short_step3["planner_input"]["request"]["retrieved_memory"], []
        )
        self.assertEqual(
            no_step3["planner_decision"]["action"],
            short_step3["planner_decision"]["action"],
        )
        self.assertEqual(
            no_step3["planner_decision"]["reason_code"], "systematic_search"
        )
        self.assertEqual(
            short_step3["planner_decision"]["reason_code"], "systematic_search"
        )
        self.assertEqual(
            object_step3["planner_input"]["request"]["retrieved_memory"][0][
                "source_observation_id"
            ],
            "observation:0",
        )
        self.assertTrue(object_step3["planner_decision"]["memory_guided"])
        self.assertEqual(summaries["object_memory"]["steps"], 4)
        self.assertEqual(summaries["no_memory"]["steps"], 6)
        self.assertEqual(summaries["short_memory_k2"]["steps"], 6)

    def test_missing_initial_cup_fails_without_reusing_book_setup_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            output_dir = Path(temporary_dir) / "missing_cup"
            summary = ThorEpisodeRunner(
                ThorEpisodeConfig(
                    task="thor_cup_after_coffee_subgoal",
                    output_dir=output_dir,
                    save_frames=False,
                    trace_html=False,
                ),
                env=_CupCoffeeThorEnv(cup_visible_at_reset=False),
            ).run()

            self.assertFalse(summary["success"])
            self.assertEqual(summary["setup_action_count"], 0)
            self.assertEqual(summary["planner_call_count"], 0)
            self.assertIn("Cup", summary["failure_reason"])
            self.assertEqual(len(self._jsonl(output_dir / "setup.jsonl")), 1)

    def test_order_audit_rejects_cup_pickup_before_coffee_machine(self) -> None:
        progress = CupAfterCoffeeProgress()
        initial = {
            "objects": [
                {
                    "objectType": "Cup",
                    "objectId": "Cup|1",
                    "visible": True,
                    "pickupable": True,
                }
            ]
        }
        progress.initialize(initial)
        progress.observe_action(
            step=1,
            action={"action": "PickupObject", "objectId": "Cup|1"},
            success=True,
            observation_after={"objects": []},
        )
        snapshot = progress.snapshot()
        self.assertFalse(snapshot["ordered_subgoal_passed"])
        self.assertEqual(
            snapshot["protocol_violations"],
            ["cup_picked_before_coffee_machine_at_step:1"],
        )

    def test_visible_distant_coffee_machine_is_approached_before_toggle(self) -> None:
        observation = {
            "agent": {
                "position": {"x": 0.0, "y": 0.9, "z": 0.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "cameraHorizon": 0.0,
            },
            "objects": [
                {
                    "objectType": "CoffeeMachine",
                    "objectId": "CoffeeMachine|far",
                    "position": {"x": 0.0, "y": 0.9, "z": 2.0},
                    "visible": True,
                    "toggleable": True,
                }
            ],
            "inventory": [],
        }
        request = PlannerRequest(
            task_name="thor_cup_after_coffee_subgoal",
            instruction="Toggle CoffeeMachine before Cup pickup.",
            task_stage="toggle_coffee_machine",
            step=2,
            max_steps=16,
            observation=observation,
            allowed_actions=THOR_CUP_COFFEE_ACTIONS,
        )
        decision = ThorBookReacquirePlanner().plan(request)
        self.assertEqual(decision.action, {"action": "MoveAhead"})
        self.assertEqual(decision.target_object_type, "CoffeeMachine")
        self.assertEqual(decision.reason_code, "approach_visible_target")
        self.assertFalse(decision.memory_guided)

    @staticmethod
    def _jsonl(path: Path) -> list[dict[str, Any]]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
        ]


if __name__ == "__main__":
    unittest.main()

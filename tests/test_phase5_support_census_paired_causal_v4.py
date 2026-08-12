"""Offline tests for the paired-causal support census successor."""

from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    ROOT / "scripts" / "census_phase5_r1_supports_paired_causal_v4.py"
)
CONFIG_PATH = (
    ROOT / "configs" / "phase5_r1_support_census_paired_causal_v4.json"
)


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "census_phase5_r1_supports_paired_causal_v4", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Event:
    def __init__(self, metadata: Mapping[str, Any]) -> None:
        self.metadata = dict(metadata)


class _PairedCausalEnv:
    SUPPORT_TYPES = (
        "Bed",
        "CoffeeTable",
        "CounterTop",
        "Desk",
        "DiningTable",
        "Dresser",
        "Shelf",
        "SideTable",
    )

    def __init__(
        self,
        *,
        control_rotation_delta: float = 0.2,
        query_rotation_delta: float = 0.2,
        extra_query_type: str | None = None,
        failed_query_types: set[str] | None = None,
        control_logical_change: bool = False,
    ) -> None:
        self.control_rotation_delta = control_rotation_delta
        self.query_rotation_delta = query_rotation_delta
        self.extra_query_type = extra_query_type
        self.failed_query_types = set(failed_query_types or set())
        self.control_logical_change = control_logical_change
        self.reset_scenes: list[str] = []
        self.action_batches: list[list[dict[str, Any]]] = []
        self._actions_since_reset: list[dict[str, Any]] = []
        self._base_objects = [
            {
                "objectId": "Book|private",
                "objectType": "Book",
                "pickupable": True,
                "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "parentReceptacles": ["Desk|private"],
                "isMoving": False,
                "isPickedUp": False,
                "isOpen": False,
            },
            *[
                {
                    "objectId": f"{support_type}|private",
                    "objectType": support_type,
                    "receptacle": True,
                    "visible": support_type == "Desk",
                    "position": {"x": float(index + 1), "y": 1.0, "z": 0.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "parentReceptacles": None,
                    "isMoving": False,
                    "isPickedUp": False,
                    "isOpen": False,
                }
                for index, support_type in enumerate(self.SUPPORT_TYPES)
            ],
        ]
        self._objects = deepcopy(self._base_objects)

    def reset(self, scene: str) -> _Event:
        if self._actions_since_reset:
            self.action_batches.append(self._actions_since_reset)
        self._actions_since_reset = []
        self.reset_scenes.append(scene)
        self._objects = deepcopy(self._base_objects)
        return _Event({"objects": deepcopy(self._objects)})

    def step(self, action: Mapping[str, Any]) -> _Event:
        recorded = dict(action)
        self._actions_since_reset.append(recorded)
        action_name = str(action["action"])
        success = True
        returned: Any = None
        if action_name == "GetReachablePositions":
            returned = [{"x": 0.0, "y": 0.9, "z": 0.0}]
        elif action_name == "Pass":
            if len(self._actions_since_reset) == 6:
                self._objects[0]["rotation"]["y"] = self.control_rotation_delta
                if self.control_logical_change:
                    self._objects[0]["isOpen"] = True
        elif action_name == "GetSpawnCoordinatesAboveReceptacle":
            support_type = str(action["objectId"]).split("|", 1)[0]
            delta = self.query_rotation_delta
            if support_type == self.extra_query_type:
                delta += 0.2
            self._objects[0]["rotation"]["y"] = delta
            success = support_type not in self.failed_query_types
            returned = (
                [{"x": 9.0, "y": 9.0, "z": 9.0}] if success else None
            )
        else:
            raise AssertionError(f"forbidden action reached fake env: {action_name}")
        return _Event(
            {
                "objects": deepcopy(self._objects),
                "lastActionSuccess": success,
                "actionReturn": returned,
            }
        )

    def get_evaluator_state(self) -> dict[str, Any]:
        return {"objects": deepcopy(self._objects)}


class Phase5SupportCensusPairedCausalV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()
        cls.config = cls.module.load_config(CONFIG_PATH)

    def _run_scene(self, env: _PairedCausalEnv) -> dict[str, Any]:
        return self.module.census_scene(
            env,
            scene="FloorPlanFixture",
            support_types=self.config["candidate_receptacle_types"],
            settling_pass_count=self.config["settling_pass_count"],
            thresholds=self.config["causal_excess_thresholds"],
        )

    def test_config_freezes_six_scenes_pairing_and_scope(self) -> None:
        self.assertEqual(
            self.config["inspected_scenes"],
            [
                "FloorPlan202",
                "FloorPlan301",
                "FloorPlan302",
                "FloorPlan303",
                "FloorPlan304",
                "FloorPlan305",
            ],
        )
        self.assertTrue(self.config["fresh_reset_per_trial"])
        self.assertTrue(self.config["spawn_query_anywhere"])
        self.assertEqual(
            self.config["allowed_actions"],
            [
                "GetReachablePositions",
                "GetSpawnCoordinatesAboveReceptacle",
                "Pass",
            ],
        )
        self.assertTrue(
            all(value is False for value in self.config["constraints"].values())
        )

    def test_causal_comparison_ignores_absolute_background_jitter(self) -> None:
        query = {
            "identity_set_changed": False,
            "logical_digest_changed": False,
            "max_position_delta_meters": 0.002,
            "max_rotation_component_delta_degrees": 0.25,
            "material_change": True,
        }
        control = {
            "identity_set_changed": False,
            "logical_digest_changed": False,
            "max_position_delta_meters": 0.002,
            "max_rotation_component_delta_degrees": 0.24,
            "material_change": True,
        }
        result = self.module.compare_query_to_matched_control(
            query,
            control,
            position_excess_threshold=0.001,
            rotation_excess_threshold=0.1,
        )
        self.assertFalse(result["causal_material_query_effect"])
        self.assertAlmostEqual(result["positive_rotation_excess_degrees"], 0.01)
        self.assertTrue(result["absolute_query_material_change_ignored"])
        self.assertTrue(result["absolute_control_material_change_ignored"])

    def test_causal_comparison_detects_query_excess(self) -> None:
        query = {
            "identity_set_changed": False,
            "logical_digest_changed": False,
            "max_position_delta_meters": 0.0,
            "max_rotation_component_delta_degrees": 0.35,
        }
        control = {
            "identity_set_changed": False,
            "logical_digest_changed": False,
            "max_position_delta_meters": 0.0,
            "max_rotation_component_delta_degrees": 0.2,
        }
        result = self.module.compare_query_to_matched_control(
            query,
            control,
            position_excess_threshold=0.001,
            rotation_excess_threshold=0.1,
        )
        self.assertTrue(result["causal_material_query_effect"])
        self.assertAlmostEqual(result["positive_rotation_excess_degrees"], 0.15)

    def test_every_query_has_fresh_reset_matched_pass_and_alternating_order(self) -> None:
        env = _PairedCausalEnv()
        row = self._run_scene(env)
        self.assertTrue(row["scene_complete"])
        self.assertEqual(row["expected_pair_count"], 8)
        self.assertEqual(row["completed_pair_count"], 8)
        self.assertTrue(row["all_pairs_fresh_reset"])
        self.assertFalse(row["absolute_changes_used_for_decision"])
        pairs = [
            pair
            for support in row["support_types"]
            for pair in support["pairs"]
        ]
        self.assertEqual(
            [pair["pair_order"] for pair in pairs],
            [
                "query_then_pass",
                "pass_then_query",
                "query_then_pass",
                "pass_then_query",
                "query_then_pass",
                "pass_then_query",
                "query_then_pass",
                "pass_then_query",
            ],
        )
        queries = [
            action
            for batch in env.action_batches + [env._actions_since_reset]
            for action in batch
            if action["action"] == "GetSpawnCoordinatesAboveReceptacle"
        ]
        self.assertEqual(len(queries), 8)
        self.assertTrue(all(action["anywhere"] is True for action in queries))
        self.assertEqual(len(env.reset_scenes), 17)

    def test_query_failure_is_availability_not_false_mutation(self) -> None:
        row = self._run_scene(_PairedCausalEnv(failed_query_types={"Shelf"}))
        self.assertTrue(row["scene_complete"])
        self.assertFalse(row["causal_query_effect_detected"])
        shelf = next(
            item for item in row["support_types"] if item["support_type"] == "Shelf"
        )
        self.assertEqual(shelf["error_type_summary"], {"action_failed": 1})
        self.assertEqual(shelf["positive_query_count"], 0)

    def test_causal_effect_and_control_integrity_each_stop_the_scene(self) -> None:
        effect = self._run_scene(_PairedCausalEnv(extra_query_type="Desk"))
        self.assertEqual(effect["stop_category"], "causal_material_query_effect")
        self.assertFalse(effect["scene_complete"])
        background = self._run_scene(
            _PairedCausalEnv(control_logical_change=True)
        )
        self.assertEqual(
            background["stop_category"],
            "matched_control_background_integrity_change",
        )
        self.assertFalse(background["scene_complete"])

    def test_policy_candidate_ignores_placement_outcomes(self) -> None:
        row = self._run_scene(_PairedCausalEnv(failed_query_types={"Shelf"}))
        scenes = [
            {**deepcopy(row), "scene": scene}
            for scene in self.config["inspected_scenes"]
        ]
        baseline = self.module.build_policy_candidate(self.config, scenes)
        contaminated = deepcopy(scenes)
        for index, scene in enumerate(contaminated):
            scene["placement_success"] = index % 2 == 0
        self.assertEqual(
            baseline,
            self.module.build_policy_candidate(self.config, contaminated),
        )
        self.assertNotIn("Shelf", baseline["admitted_support_types"])
        self.assertFalse(baseline["placement_outcomes_used"])
        self.assertFalse(baseline["formal_use_allowed"])

    def test_public_summary_is_complete_private_safe_and_non_experimental(self) -> None:
        row = self._run_scene(_PairedCausalEnv())
        scenes = [
            {**deepcopy(row), "scene": scene}
            for scene in self.config["inspected_scenes"]
        ]
        summary = self.module.build_public_summary(
            config=self.config,
            scenes=scenes,
            git_state={"code_revision": "a" * 40, "working_tree_dirty": False},
            raw_digest="b" * 64,
        )
        self.assertTrue(summary["passed"])
        self.assertTrue(summary["every_support_query_has_matched_pass"])
        self.assertFalse(
            summary["absolute_one_action_pose_changes_used_for_decision"]
        )
        self.assertFalse(summary["placement_actions_run"])
        self.assertFalse(summary["pickup_actions_run"])
        self.assertFalse(summary["fallback_route_run"])
        self.assertFalse(summary["memory_agents_run"])
        serialized = json.dumps(summary, sort_keys=True)
        for forbidden in (
            '"objectId"',
            '"position"',
            '"rotation"',
            '"x"',
            '"y"',
            '"z"',
            "target_point",
            "private_registry",
            "PlaceObjectAtPoint",
            "PickupObject",
            "forceAction",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()

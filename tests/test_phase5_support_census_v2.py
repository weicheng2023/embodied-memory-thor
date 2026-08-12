"""Offline tests for reset-isolated tolerant support census v2."""

from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "census_phase5_r1_supports_v2.py"
CONFIG_PATH = ROOT / "configs" / "phase5_r1_support_census_v2.json"
EVIDENCE_PATH = ROOT / "docs" / "evidence" / "phase5_r1_support_census_v2.json"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "census_phase5_r1_supports_v2", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Event:
    def __init__(self, metadata: Mapping[str, Any]) -> None:
        self.metadata = dict(metadata)


class _ResetIsolatedEnv:
    def __init__(
        self,
        *,
        failed_types: set[str] | None = None,
        material_type: str | None = None,
    ) -> None:
        self.failed_types = set(failed_types or set())
        self.material_type = material_type
        self.reset_scenes: list[str] = []
        self.actions_since_reset: list[str] = []
        self.max_queries_between_resets = 0
        self._query_count = 0
        self._base_objects = [
            {
                "objectId": "Book|private",
                "objectType": "Book",
                "pickupable": True,
                "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "parentReceptacles": ["Bed|private"],
                "isMoving": False,
                "isPickedUp": False,
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
                }
                for index, support_type in enumerate(
                    (
                        "Bed",
                        "CoffeeTable",
                        "CounterTop",
                        "Desk",
                        "DiningTable",
                        "Dresser",
                        "Shelf",
                        "SideTable",
                    )
                )
            ],
        ]
        self._objects = deepcopy(self._base_objects)

    def reset(self, scene: str) -> _Event:
        self.max_queries_between_resets = max(
            self.max_queries_between_resets, self._query_count
        )
        self._query_count = 0
        self.actions_since_reset = []
        self.reset_scenes.append(scene)
        self._objects = deepcopy(self._base_objects)
        return _Event({"objects": deepcopy(self._objects)})

    def step(self, action: Mapping[str, Any]) -> _Event:
        action_name = str(action["action"])
        self.actions_since_reset.append(action_name)
        success = True
        if action_name == "Pass":
            returned = None
        elif action_name == "GetReachablePositions":
            returned = [{"x": 0.0, "y": 0.9, "z": 0.0}]
        else:
            self._query_count += 1
            support_type = str(action["objectId"]).split("|", 1)[0]
            success = support_type not in self.failed_types
            returned = [{"x": 9.0, "y": 9.0, "z": 9.0}] if success else None
            if support_type == self.material_type:
                self._objects[0]["position"]["x"] += 0.01
        return _Event(
            {
                "objects": deepcopy(self._objects),
                "lastActionSuccess": success,
                "actionReturn": returned,
            }
        )

    def get_evaluator_state(self) -> dict[str, Any]:
        return {"objects": deepcopy(self._objects)}


class Phase5SupportCensusV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()
        cls.config = cls.module.load_config(CONFIG_PATH)

    def _run_scene(self, env: _ResetIsolatedEnv) -> dict[str, Any]:
        thresholds = self.config["material_change_thresholds"]
        return self.module.census_scene(
            env,
            scene="FloorPlanFixture",
            support_types=self.config["candidate_receptacle_types"],
            settling_pass_count=self.config["settling_pass_count"],
            position_threshold=thresholds["position_delta_meters"],
            rotation_threshold=thresholds["rotation_component_delta_degrees"],
        )

    def test_config_freezes_reset_isolation_thresholds_and_order(self) -> None:
        self.assertEqual(
            self.config["census_version"], "phase5-r1-support-census-v2"
        )
        self.assertEqual(self.config["settling_pass_count"], 5)
        self.assertTrue(self.config["one_receptacle_query_per_reset"])
        self.assertEqual(
            self.config["material_change_thresholds"],
            {
                "position_delta_meters": 0.001,
                "rotation_component_delta_degrees": 0.1,
            },
        )
        self.assertEqual(
            self.config["candidate_receptacle_types"],
            sorted(self.config["candidate_receptacle_types"]),
        )

    def test_every_receptacle_query_is_reset_isolated(self) -> None:
        env = _ResetIsolatedEnv(failed_types={"Shelf", "SideTable"})
        row = self._run_scene(env)
        env.reset("FloorPlanFixture")
        self.assertTrue(row["every_query_reset_isolated"])
        self.assertEqual(env.max_queries_between_resets, 1)
        self.assertFalse(row["material_mutation_detected"])
        shelf = next(
            item for item in row["support_types"] if item["support_type"] == "Shelf"
        )
        self.assertEqual(shelf["error_type_summary"], {"action_failed": 1})
        self.assertEqual(shelf["material_mutation_query_count"], 0)

    def test_material_query_mutation_is_detected(self) -> None:
        row = self._run_scene(_ResetIsolatedEnv(material_type="Desk"))
        self.assertTrue(row["material_mutation_detected"])
        desk = next(
            item for item in row["support_types"] if item["support_type"] == "Desk"
        )
        self.assertEqual(desk["material_mutation_query_count"], 1)
        self.assertGreater(desk["max_position_delta_meters"], 0.001)

    def test_policy_uses_census_not_placement_outcomes(self) -> None:
        row = self._run_scene(
            _ResetIsolatedEnv(failed_types={"Shelf", "SideTable"})
        )
        scenes = [{**deepcopy(row), "scene": scene} for scene in self.config["inspected_scenes"]]
        first = self.module.build_policy_candidate(self.config, scenes)
        contaminated = deepcopy(scenes)
        for index, scene in enumerate(contaminated):
            scene["placement_success"] = index % 2 == 0
        second = self.module.build_policy_candidate(self.config, contaminated)
        self.assertEqual(first, second)
        self.assertNotIn("Shelf", first["admitted_support_types"])
        self.assertNotIn("SideTable", first["admitted_support_types"])
        self.assertFalse(first["placement_outcomes_used"])
        self.assertFalse(first["formal_use_allowed"])

    def test_public_summary_discards_comparisons_and_private_fields(self) -> None:
        row = self._run_scene(_ResetIsolatedEnv())
        scenes = [{**deepcopy(row), "scene": scene} for scene in self.config["inspected_scenes"]]
        summary = self.module.build_public_summary(
            config=self.config,
            raw_scene_rows=scenes,
            git_state={"code_revision": "a" * 40, "working_tree_dirty": False},
            raw_digest="b" * 64,
        )
        self.assertTrue(summary["passed"])
        serialized = json.dumps(summary, sort_keys=True)
        for forbidden in (
            "objectId",
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
            "private_comparisons",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(summary["placement_actions_run"])
        self.assertFalse(summary["memory_agents_run"])
        self.assertFalse(summary["images_saved"])

    def test_real_census_stop_is_incomplete_private_and_non_selective(self) -> None:
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        review = evidence["post_run_review"]

        self.assertFalse(evidence["passed"])
        self.assertFalse(evidence["census_complete"])
        self.assertEqual(evidence["scene_count"], 3)
        self.assertEqual(evidence["fatal_error_category"], "material_query_mutation")
        self.assertIsNone(evidence["support_policy_candidate"])
        self.assertFalse(evidence["support_policy_recommendation_available"])
        self.assertEqual(
            review["started_scenes"],
            ["FloorPlan202", "FloorPlan301", "FloorPlan302"],
        )
        self.assertEqual(
            review["not_started_scenes"],
            ["FloorPlan303", "FloorPlan304", "FloorPlan305"],
        )
        self.assertFalse(review["floorplan301_restart_allowed"])
        self.assertFalse(review["query_parameter_alignment_with_qualifier"])
        self.assertFalse(review["census_query_anywhere"])
        self.assertTrue(review["qualifier_query_anywhere"])
        self.assertFalse(evidence["placement_actions_run"])
        self.assertFalse(evidence["pickup_actions_run"])
        self.assertFalse(evidence["fallback_route_run"])
        self.assertFalse(evidence["memory_agents_run"])
        self.assertFalse(evidence["images_saved"])

        serialized = json.dumps(evidence, sort_keys=True)
        for forbidden in (
            "objectId",
            '"position"',
            '"rotation"',
            '"x"',
            '"y"',
            '"z"',
            "target_point",
            "private_registry",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()

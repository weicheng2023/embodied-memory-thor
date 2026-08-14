"""Offline acceptance tests for the read-only Phase 5 support census."""

from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "census_phase5_r1_supports.py"
CONFIG_PATH = ROOT / "configs" / "phase5_r1_support_census.json"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "census_phase5_r1_supports", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Event:
    def __init__(self, metadata: Mapping[str, Any]) -> None:
        self.metadata = dict(metadata)


class _ReadOnlyEnv:
    def __init__(self) -> None:
        self.actions: list[dict[str, Any]] = []
        self._objects = [
            {
                "objectId": "Book|private",
                "objectType": "Book",
                "pickupable": True,
                "visible": True,
                "position": {"x": 1.0, "y": 1.0, "z": 1.0},
            },
            {
                "objectId": "Desk|private",
                "objectType": "Desk",
                "receptacle": True,
                "visible": False,
                "position": {"x": 2.0, "y": 1.0, "z": 2.0},
            },
        ]

    def reset(self, scene: str) -> _Event:
        return _Event({"objects": deepcopy(self._objects), "sceneName": scene})

    def step(self, action: Mapping[str, Any]) -> _Event:
        self.actions.append(dict(action))
        if action["action"] == "GetReachablePositions":
            returned = [{"x": 0.0, "y": 0.9, "z": 0.0}]
        else:
            returned = [{"x": 2.0, "y": 1.1, "z": 2.0}]
        return _Event(
            {
                "objects": deepcopy(self._objects),
                "lastActionSuccess": True,
                "actionReturn": returned,
            }
        )

    def get_evaluator_state(self) -> dict[str, Any]:
        return {"objects": deepcopy(self._objects)}


class Phase5SupportCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()
        cls.config = cls.module.load_census_config(CONFIG_PATH)

    def _scene_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        support_types = [
            row["support_type"]
            for row in self.config["candidate_receptacle_types"]
        ]
        for scene in self.config["inspected_scenes"]:
            typed = []
            for support_type in support_types:
                present = support_type in {"Bed", "Desk", "SideTable"}
                typed.append(
                    {
                        "support_type": support_type,
                        "metadata_count": int(present),
                        "receptacle_true_count": int(present),
                        "visible_receptacle_count": 0,
                        "nonvisible_receptacle_count": int(present),
                        "spawn_query_attempt_count": int(present),
                        "spawn_query_success_count": int(present),
                        "positive_spawn_query_count": int(present),
                        "spawn_coordinate_count": 10 if present else 0,
                        "error_type_summary": {},
                    }
                )
            rows.append(
                {
                    "scene": scene,
                    "reset_success": True,
                    "reachable_query_success": True,
                    "reachable_count": 20,
                    "pickupable_book_count": 1,
                    "support_types": typed,
                    "state_unchanged_after_spawn_queries": True,
                    "last_action_isolated_by_next_scene_reset": True,
                    "allowed_action_count": 4,
                    "unexpected_action_count": 0,
                    "private_state_digest_before": "a" * 64,
                    "private_state_digest_after": "a" * 64,
                }
            )
        return rows

    def test_config_freezes_six_scenes_and_deterministic_support_order(self) -> None:
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
        support_types = [
            row["support_type"]
            for row in self.config["candidate_receptacle_types"]
        ]
        self.assertEqual(support_types, sorted(support_types))
        self.assertTrue(
            {
                "Desk",
                "Dresser",
                "SideTable",
                "CoffeeTable",
                "DiningTable",
                "CounterTop",
                "Bed",
                "Shelf",
            }.issubset(support_types)
        )

    def test_scene_census_calls_only_read_only_actions_and_discards_coordinates(self) -> None:
        env = _ReadOnlyEnv()
        row = self.module.census_scene(
            env,
            scene="FloorPlanFixture",
            support_types=["Bed", "Desk"],
        )
        self.assertEqual(
            {action["action"] for action in env.actions},
            {
                "GetReachablePositions",
                "GetSpawnCoordinatesAboveReceptacle",
            },
        )
        self.assertTrue(row["state_unchanged_after_spawn_queries"])
        self.assertEqual(row["unexpected_action_count"], 0)
        self.assertNotIn("objectId", json.dumps(row))
        self.assertNotIn('"x"', json.dumps(row))

    def test_public_summary_has_no_private_fields_or_actions(self) -> None:
        summary = self.module.build_public_summary(
            config=self.config,
            raw_scene_rows=self._scene_rows(),
            git_state={"code_revision": "a" * 40, "working_tree_dirty": False},
            raw_digest="b" * 64,
        )
        self.assertTrue(summary["passed"])
        serialized = json.dumps(summary, sort_keys=True)
        for forbidden in (
            "objectId",
            '"position"',
            '"x"',
            '"y"',
            '"z"',
            "target_point",
            "private_registry",
            "PlaceObjectAtPoint",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(summary["placement_actions_run"])
        self.assertFalse(summary["memory_agents_run"])
        self.assertFalse(summary["images_saved"])

    def test_policy_candidate_is_deterministic_and_ignores_placement_outcomes(self) -> None:
        rows = self._scene_rows()
        first = self.module.build_policy_candidate(self.config, rows)
        contaminated = deepcopy(rows)
        for index, row in enumerate(contaminated):
            row["placement_success"] = index % 2 == 0
        second = self.module.build_policy_candidate(self.config, contaminated)
        self.assertEqual(first, second)
        self.assertEqual(
            first["admitted_support_types"], ["Bed", "Desk", "SideTable"]
        )
        self.assertFalse(first["placement_outcomes_used"])
        self.assertFalse(first["formal_use_allowed"])

    def test_retained_floorplan_evidence_remains_readable(self) -> None:
        stopped = json.loads(
            (
                ROOT
                / "docs"
                / "evidence"
                / "phase5_floorplan301_axis_aware_v2_geometry_stop.json"
            ).read_text(encoding="utf-8")
        )
        passed = json.loads(
            (
                ROOT
                / "docs"
                / "evidence"
                / "phase5_floorplan202_axis_aware_v2_anchor_qualification.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(stopped["passed"])
        self.assertEqual(stopped["accepted_geometry_candidate_count"], 0)
        self.assertTrue(passed["qualification"]["passed"])
        self.assertEqual(
            passed["geometry_version"],
            "phase5-axis-aware-rectangular-footprint-v2",
        )

    def test_failed_real_census_evidence_is_private_free_and_blocks_policy(self) -> None:
        evidence_path = (
            ROOT / "docs" / "evidence" / "phase5_r1_support_census.json"
        )
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.module.audit_public_summary(evidence)
        self.assertFalse(evidence["passed"])
        self.assertFalse(evidence["census_complete"])
        self.assertEqual(evidence["scene_count"], 1)
        self.assertEqual(
            evidence["fatal_error_category"], "unexpected_state_mutation"
        )
        self.assertFalse(evidence["support_policy_recommendation_available"])
        self.assertFalse(evidence["floorplan301_restart_allowed"])
        self.assertFalse(evidence["placement_actions_run"])
        self.assertFalse(evidence["memory_agents_run"])


if __name__ == "__main__":
    unittest.main()

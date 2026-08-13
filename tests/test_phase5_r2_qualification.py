"""Offline tests for ordered R2 qualification route construction."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from embodied_memory_thor.phase5.r2 import (
    build_task_subgoal_route,
    normalize_interactable_pose,
    route_action_codes,
    shortest_grid_path,
)


class Phase5R2QualificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reachable = [
            {"x": x * 0.25, "y": 0.9, "z": z * 0.25}
            for x, z in ((0, 0), (0, 1), (0, 2), (1, 2), (2, 2))
        ]

    def test_shortest_path_and_action_route_are_deterministic(self) -> None:
        start = {
            "x": 0.0,
            "y": 0.9,
            "z": 0.0,
            "rotation": 90.0,
            "horizon": 0.0,
            "standing": True,
        }
        destination = {
            "x": 0.5,
            "y": 0.9,
            "z": 0.5,
            "rotation": 180.0,
            "horizon": 30.0,
            "standing": True,
        }
        self.assertEqual(
            shortest_grid_path(
                reachable_positions=self.reachable,
                start_pose=start,
                destination_pose=destination,
            ),
            [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2)],
        )
        route = build_task_subgoal_route(
            reachable_positions=self.reachable,
            start_pose=start,
            destination_pose=destination,
        )
        self.assertEqual(route_action_codes(route), "LFFRFFR D".replace(" ", ""))
        self.assertTrue(route["qualification_goal_input_used"])
        self.assertTrue(route["target_or_anchor_input_used"])
        self.assertFalse(route["runtime_coordinate_input_used"])

    def test_pose_normalization_accepts_mapping_rotation(self) -> None:
        pose = normalize_interactable_pose(
            {
                "x": 1,
                "y": 0.9,
                "z": -1,
                "rotation": {"y": -90},
                "cameraHorizon": 30,
                "standing": True,
            }
        )
        self.assertEqual(pose["rotation"], 270.0)
        self.assertEqual(pose["horizon"], 30.0)

    def test_off_grid_pose_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "reachable-position grid"):
            shortest_grid_path(
                reachable_positions=self.reachable,
                start_pose={"x": 4.0, "z": 4.0},
                destination_pose={"x": 0.0, "z": 0.0},
            )

    def test_cup_selection_checks_sorted_ids_on_fresh_resets_and_stops_at_first_pass(
        self,
    ) -> None:
        module = self._qualifier_module()

        class _CupSelectionEnv:
            def __init__(self) -> None:
                self.reset_count = 0
                self.query_log: list[tuple[int, str]] = []
                self.metadata: dict[str, Any] = {}

            def reset(self, scene: str) -> Any:
                self.reset_count += 1
                self.metadata = {
                    "sceneName": scene,
                    "objects": [
                        {"objectType": "Cup", "objectId": object_id, "pickupable": True}
                        for object_id in ("Cup|c", "Cup|a", "Cup|b")
                    ],
                }
                return SimpleNamespace(metadata=self.metadata)

            def get_evaluator_state(self) -> Mapping[str, Any]:
                return self.metadata

            def step(self, action: Mapping[str, Any]) -> Any:
                object_id = str(action["objectId"])
                self.query_log.append((self.reset_count, object_id))
                return SimpleNamespace(
                    metadata={
                        "lastActionSuccess": True,
                        "errorMessage": "",
                        "actionReturn": [{
                            "x": 0.0,
                            "y": 0.9,
                            "z": 0.0,
                            "rotation": 0.0,
                            "horizon": 0.0,
                            "standing": object_id != "Cup|a",
                        }],
                    }
                )

        env = _CupSelectionEnv()
        selected, poses, audit = module._select_first_standing_interactable_cup(
            env, scene="FloorPlan1"
        )
        self.assertEqual(selected["objectId"], "Cup|b")
        self.assertEqual([row["object_id"] for row in audit], ["Cup|a", "Cup|b"])
        self.assertEqual(env.query_log, [(2, "Cup|a"), (3, "Cup|b")])
        self.assertTrue(all(row["fresh_reset_before_query"] for row in audit))
        self.assertEqual(audit[0]["standing_pose_count"], 0)
        self.assertFalse(audit[0]["selected"])
        self.assertEqual(audit[1]["standing_pose_count"], 1)
        self.assertTrue(audit[1]["selected"])
        self.assertTrue(poses[0]["standing"])
        self.assertNotIn("Cup|c", [row["object_id"] for row in audit])

    def test_cup_selection_returns_full_failure_audit_when_none_standing(self) -> None:
        module = self._qualifier_module()

        class _NoStandingEnv:
            def __init__(self) -> None:
                self.metadata: dict[str, Any] = {}
                self.queries: list[str] = []

            def reset(self, scene: str) -> Any:
                self.metadata = {
                    "sceneName": scene,
                    "objects": [
                        {"objectType": "Cup", "objectId": object_id, "pickupable": True}
                        for object_id in ("Cup|b", "Cup|a")
                    ],
                }
                return SimpleNamespace(metadata=self.metadata)

            def get_evaluator_state(self) -> Mapping[str, Any]:
                return self.metadata

            def step(self, action: Mapping[str, Any]) -> Any:
                self.queries.append(str(action["objectId"]))
                return SimpleNamespace(
                    metadata={
                        "lastActionSuccess": True,
                        "errorMessage": "",
                        "actionReturn": [{
                            "x": 0.0,
                            "y": 0.9,
                            "z": 0.0,
                            "rotation": 0.0,
                            "horizon": 0.0,
                            "standing": False,
                        }],
                    }
                )

        env = _NoStandingEnv()
        selected, poses, audit = module._select_first_standing_interactable_cup(
            env, scene="FloorPlan1"
        )
        self.assertIsNone(selected)
        self.assertEqual(poses, [])
        self.assertEqual(env.queries, ["Cup|a", "Cup|b"])
        self.assertEqual(len(audit), 2)
        self.assertTrue(all(not row["selected"] for row in audit))

    def test_cup_selection_query_failure_is_fatal(self) -> None:
        module = self._qualifier_module()

        class _QueryFailureEnv:
            def __init__(self) -> None:
                self.metadata: dict[str, Any] = {}

            def reset(self, scene: str) -> Any:
                self.metadata = {
                    "sceneName": scene,
                    "objects": [{
                        "objectType": "Cup",
                        "objectId": "Cup|a",
                        "pickupable": True,
                    }],
                }
                return SimpleNamespace(metadata=self.metadata)

            def get_evaluator_state(self) -> Mapping[str, Any]:
                return self.metadata

            def step(self, action: Mapping[str, Any]) -> Any:
                return SimpleNamespace(metadata={
                    "lastActionSuccess": False,
                    "errorMessage": "simulated query failure",
                    "actionReturn": None,
                })

        with self.assertRaisesRegex(
            RuntimeError, "GetInteractablePoses failed for Cup order 1"
        ):
            module._select_first_standing_interactable_cup(
                _QueryFailureEnv(), scene="FloorPlan1"
            )

    def test_kitchen_scene_range_is_explicit(self) -> None:
        module = self._qualifier_module()
        self.assertEqual(module._kitchen_scene_number("FloorPlan1"), 1)
        self.assertEqual(module._kitchen_scene_number("FloorPlan2"), 2)
        self.assertEqual(module._kitchen_scene_number("FloorPlan30"), 30)
        for scene in ("FloorPlan0", "FloorPlan31", "FloorPlan201", "FloorPlan"):
            with self.subTest(scene=scene):
                with self.assertRaisesRegex(ValueError, "FloorPlan1-FloorPlan30"):
                    module._kitchen_scene_number(scene)

    def test_no_standing_cup_has_scene_skippable_class(self) -> None:
        module = self._qualifier_module()
        error = module.SceneStartIneligibleError("no standing Cup")
        self.assertIsInstance(error, RuntimeError)

    @staticmethod
    def _qualifier_module() -> Any:
        path = Path(__file__).resolve().parents[1] / "scripts" / "qualify_phase5_r2.py"
        spec = importlib.util.spec_from_file_location("qualify_phase5_r2", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


if __name__ == "__main__":
    unittest.main()

"""Offline tests for ordered R2 qualification route construction."""

from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()

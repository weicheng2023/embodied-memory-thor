"""Offline tests for pre-qualified relocation anchor planning."""

from __future__ import annotations

import unittest

from embodied_memory_thor.phase5.anchors import (
    build_geometry_candidate_plan,
    build_target_independent_coverage_route,
    public_anchor_reference,
    stable_digest,
)


def _box(
    object_id: str,
    *,
    x: float,
    y: float,
    z: float,
    sx: float,
    sy: float,
    sz: float,
    object_type: str,
    parents: list[str] | None = None,
) -> dict:
    return {
        "objectId": object_id,
        "objectType": object_type,
        "position": {"x": x, "y": y, "z": z},
        "parentReceptacles": list(parents or []),
        "axisAlignedBoundingBox": {
            "center": {"x": x, "y": y, "z": z},
            "size": {"x": sx, "y": sy, "z": sz},
        },
    }


class Phase5AnchorTests(unittest.TestCase):
    def test_geometry_rejects_edge_and_obstacle_then_ranks_clear_points(self) -> None:
        target = _box(
            "Book|1", x=0, y=1, z=0, sx=0.5, sy=0.06, sz=0.5,
            object_type="Book",
        )
        support = _box(
            "CounterTop|far", x=2, y=1, z=2, sx=2, sy=0.1, sz=2,
            object_type="CounterTop",
        )
        pan = _box(
            "Pan|1", x=2, y=1.1, z=2, sx=0.4, sy=0.2, sz=0.4,
            object_type="Pan", parents=["CounterTop|far"],
        )
        plan = build_geometry_candidate_plan(
            target=target,
            support_queries=[
                {
                    "support": support,
                    "coordinates": [
                        {"x": 1.05, "y": 1.05, "z": 2.0},
                        {"x": 2.0, "y": 1.05, "z": 2.0},
                        {"x": 2.65, "y": 1.05, "z": 2.65},
                        {"x": 1.4, "y": 1.05, "z": 1.4},
                    ],
                }
            ],
            all_objects=[target, support, pan],
        )
        accepted = plan["accepted_candidates"]
        self.assertEqual(len(accepted), 2)
        self.assertEqual(accepted[0]["candidate_order"], 1)
        self.assertEqual(accepted[0]["point"], {"x": 1.4, "y": 1.05, "z": 1.4})
        reasons = {item["reason"] for item in plan["geometry_rejections"]}
        self.assertEqual(
            reasons,
            {
                "book_footprint_crosses_support_boundary",
                "book_footprint_overlaps_obstacle",
            },
        )

    def test_geometry_plan_is_stable_and_outcome_independent(self) -> None:
        target = _box(
            "Book|1", x=0, y=1, z=0, sx=0.4, sy=0.1, sz=0.5,
            object_type="Book",
        )
        support = _box(
            "Desk|1", x=2, y=1, z=0, sx=2, sy=0.1, sz=1,
            object_type="Desk",
        )
        args = {
            "target": target,
            "support_queries": [
                {
                    "support": support,
                    "coordinates": [
                        {"x": 2.3, "y": 1.1, "z": 0},
                        {"x": 1.7, "y": 1.1, "z": 0},
                    ],
                }
            ],
            "all_objects": [target, support],
        }
        first = build_geometry_candidate_plan(**args)
        second = build_geometry_candidate_plan(**args)
        self.assertEqual(first, second)
        self.assertEqual(stable_digest(first), stable_digest(second))
        self.assertNotIn("placement_success", str(first))

    def test_coverage_route_visits_connected_grid_without_target_input(self) -> None:
        reachable = [
            {"x": 0.0, "y": 0.9, "z": 0.0},
            {"x": 0.25, "y": 0.9, "z": 0.0},
            {"x": 0.0, "y": 0.9, "z": 0.25},
            {"x": 0.25, "y": 0.9, "z": 0.25},
        ]
        route = build_target_independent_coverage_route(
            reachable_positions=reachable,
            start_position=reachable[0],
            start_yaw=90,
        )
        self.assertTrue(route["target_or_anchor_input_used"] is False)
        self.assertTrue(route["complete_graph_coverage"])
        self.assertEqual(route["visited_node_count"], 4)
        self.assertTrue(any(row["action"]["action"] == "MoveAhead" for row in route["actions"]))
        self.assertNotIn("Book", str(route))

    def test_public_reference_contains_no_coordinates(self) -> None:
        reference = public_anchor_reference(
            anchor_id="FloorPlan1_R1_anchor_001",
            private_registry_digest="a" * 64,
            coverage_route_digest="b" * 64,
        )
        self.assertEqual(set(reference), {
            "anchor_id", "private_registry_digest", "coverage_route_digest"
        })
        self.assertNotIn("position", str(reference))
        self.assertNotIn("target_point", str(reference))


if __name__ == "__main__":
    unittest.main()

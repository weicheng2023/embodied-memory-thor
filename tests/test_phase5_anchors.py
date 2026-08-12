"""Offline tests for pre-qualified relocation anchor planning."""

from __future__ import annotations

import unittest
import json
import importlib.util
import tempfile
from pathlib import Path

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
    @staticmethod
    def _qualifier_module():
        root = Path(__file__).resolve().parents[1]
        path = root / "scripts" / "qualify_phase5_anchors.py"
        spec = importlib.util.spec_from_file_location("qualify_phase5_anchors", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_candidate_contract_and_private_start_bind_scene_and_digest(self) -> None:
        root = Path(__file__).resolve().parents[1]
        module = self._qualifier_module()
        contract_path = root / "configs" / "phase5_r1_anchor_candidates.json"
        contract = module._load_candidate_contract(contract_path, "FloorPlan301")
        self.assertEqual(contract["configuration_id"], "FloorPlan301_R1_fixed_start_001")
        self.assertEqual(contract["coverage_route_action_count"], 106)
        self.assertEqual(
            module.stable_digest({"x": 1.0, "y": 0.9, "z": 2.0}),
            stable_digest({"x": 1.0, "y": 0.9, "z": 2.0}),
        )
        with self.assertRaisesRegex(ValueError, "exactly one row"):
            module._load_candidate_contract(contract_path, "FloorPlan999")

    def test_public_anchor_candidate_contract_has_no_exact_pose_or_object_id(self) -> None:
        root = Path(__file__).resolve().parents[1]
        raw = json.loads(
            (root / "configs" / "phase5_r1_anchor_candidates.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(len(raw["candidates"]), 6)
        self.assertEqual(
            [row["candidate_order"] for row in raw["candidates"]],
            [1, 2, 3, 4, 5, 6],
        )
        self.assertNotIn("selected_pose", str(raw))
        self.assertNotIn("target_object_id", str(raw))
        self.assertNotIn("target_point", str(raw))

    def test_private_start_digest_mismatch_stops_before_environment_creation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        module = self._qualifier_module()
        contract_path = root / "configs" / "phase5_r1_anchor_candidates.json"
        pose = {
            "x": 0.0,
            "y": 0.9,
            "z": 0.0,
            "rotation": 0.0,
            "horizon": 0.0,
            "standing": True,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "registry.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "scene": "FloorPlan301",
                                "qualified": True,
                                "selected_pose": pose,
                                "selected_pose_digest": stable_digest(pose),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "public candidate contract"):
                module._setup_actions_for_candidate(
                    scene="FloorPlan301",
                    candidate_contract=contract_path,
                    start_registries=[registry_path],
                )

    def test_local_private_registry_is_ignored_and_not_imported_by_planner_path(self) -> None:
        root = Path(__file__).resolve().parents[1]
        private_path = root / "configs" / "evaluator_only" / "phase5_anchor_registry.json"
        ordinary = json.loads(
            (root / "docs" / "evidence" / "phase5_anchor_qualification_summary.json")
            .read_text(encoding="utf-8")
        )
        if private_path.exists():
            private = json.loads(private_path.read_text(encoding="utf-8"))
            self.assertFalse(private["formal_use_allowed"])
            self.assertIn("target_point", private["anchors"][0])
        gitignore = (root / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("configs/evaluator_only/*.json", gitignore)
        self.assertNotIn("target_point", ordinary)
        self.assertNotIn("position", ordinary)
        planner_path = "\n".join(
            (root / relative).read_text(encoding="utf-8")
            for relative in (
                "src/embodied_memory_thor/phase4/contracts.py",
                "src/embodied_memory_thor/phase4/planners.py",
                "src/embodied_memory_thor/phase4/runner.py",
            )
        )
        self.assertNotIn("phase5_anchor_registry", planner_path)
        self.assertNotIn("configs/evaluator_only", planner_path)

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
            scan_spacing_steps=1,
        )
        self.assertTrue(route["target_or_anchor_input_used"] is False)
        self.assertTrue(route["complete_graph_coverage"])
        self.assertTrue(route["all_nodes_within_nominal_scan_radius"])
        self.assertGreaterEqual(route["scan_waypoint_count"], 1)
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

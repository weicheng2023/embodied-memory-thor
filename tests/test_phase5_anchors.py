"""Offline tests for pre-qualified relocation anchor planning."""

from __future__ import annotations

import unittest
import json
import importlib.util
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import Mock, patch

from embodied_memory_thor.phase5.anchors import (
    ANCHOR_GEOMETRY_VERSION,
    ANCHOR_QUALIFICATION_VERSION,
    ANCHOR_REGISTRY_VERSION,
    BOOK_SUPPORT_TYPES,
    SUPPORT_POLICY_VERSION,
    build_absolute_horizon_alignment_actions,
    build_geometry_candidate_plan,
    build_target_independent_coverage_route,
    public_anchor_reference,
    stable_digest,
)


class _Event:
    def __init__(self, metadata: Mapping[str, Any]) -> None:
        self.metadata = dict(metadata)


class _FreshSupportQueryEnv:
    def __init__(self) -> None:
        self._base_objects = [
            {
                **_box(
                    "Book|private",
                    x=0.0,
                    y=1.0,
                    z=0.0,
                    sx=0.4,
                    sy=0.08,
                    sz=0.2,
                    object_type="Book",
                ),
                "pickupable": True,
                "visible": True,
                "isMoving": False,
            },
            {
                **_box(
                    "Bed|private",
                    x=2.0,
                    y=1.0,
                    z=0.0,
                    sx=2.0,
                    sy=0.2,
                    sz=2.0,
                    object_type="Bed",
                ),
                "receptacle": True,
                "visible": False,
            },
            {
                **_box(
                    "Shelf|private",
                    x=4.0,
                    y=1.0,
                    z=0.0,
                    sx=2.0,
                    sy=0.2,
                    sz=2.0,
                    object_type="Shelf",
                ),
                "receptacle": True,
                "visible": False,
            },
        ]
        self._objects = deepcopy(self._base_objects)
        self.reset_scenes: list[str] = []
        self.queries_per_reset: list[int] = []
        self._query_count = 0
        self.query_actions: list[dict[str, Any]] = []

    def reset(self, scene: str) -> _Event:
        if self.reset_scenes:
            self.queries_per_reset.append(self._query_count)
        self._query_count = 0
        self.reset_scenes.append(scene)
        self._objects = deepcopy(self._base_objects)
        return _Event(self.get_evaluator_state())

    def step(self, action: Mapping[str, Any]) -> _Event:
        action_name = str(action["action"])
        returned: Any = None
        if action_name == "GetSpawnCoordinatesAboveReceptacle":
            self._query_count += 1
            self.query_actions.append(dict(action))
            support = next(
                obj
                for obj in self._objects
                if obj["objectId"] == action["objectId"]
            )
            point = deepcopy(support["position"])
            point["y"] = 1.2
            returned = [point]
            # Deliberately contaminate this query state. Correct isolation must
            # remove it before the next query and before geometry planning.
            self._objects[0]["position"]["x"] = 99.0
        elif action_name == "GetReachablePositions":
            returned = [
                {"x": 0.0, "y": 0.9, "z": 0.0},
                {"x": 0.25, "y": 0.9, "z": 0.0},
            ]
        else:
            raise AssertionError(f"unexpected fake action: {action_name}")
        metadata = self.get_evaluator_state()
        metadata.update(
            {"lastActionSuccess": True, "actionReturn": returned, "errorMessage": ""}
        )
        return _Event(metadata)

    def get_evaluator_state(self) -> dict[str, Any]:
        return {
            "objects": deepcopy(self._objects),
            "agent": {
                "position": {"x": 0.0, "y": 0.9, "z": 0.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "cameraHorizon": 0.0,
            },
        }


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
    def test_support_policy_v3_is_predeclared_semantic_and_not_census_selected(self) -> None:
        root = Path(__file__).resolve().parents[1]
        policy = json.loads(
            (root / "configs" / "phase5_r1_support_policy_v3.json").read_text(
                encoding="utf-8"
            )
        )
        expected = [
            "Bed",
            "CoffeeTable",
            "CounterTop",
            "Desk",
            "DiningTable",
            "Dresser",
            "Shelf",
            "SideTable",
        ]
        self.assertEqual(policy["policy_version"], SUPPORT_POLICY_VERSION)
        self.assertEqual(policy["admitted_support_types"], expected)
        self.assertEqual(BOOK_SUPPORT_TYPES, frozenset(expected))
        self.assertEqual(
            ANCHOR_QUALIFICATION_VERSION, "phase5-anchor-qualification-v3"
        )
        self.assertEqual(
            ANCHOR_REGISTRY_VERSION, "phase5-private-anchor-registry-v3"
        )
        self.assertTrue(policy["one_support_query_per_fresh_reset"])
        self.assertFalse(policy["query_state_reused_by_later_query_or_trial"])
        self.assertFalse(policy["placement_outcomes_used_for_support_type_admission"])
        self.assertFalse(policy["formal_episode_dynamic_spawn_query_allowed"])
        self.assertTrue(policy["formal_episode_uses_frozen_anchor_only"])
        self.assertIn(
            "phase5_r1_support_census_paired_causal_v4.json",
            policy["retained_failed_evidence"],
        )

    def test_floorplan301_v3_launch_stop_is_pre_environment_and_private_safe(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan301_support_policy_v3_launch_stop.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            evidence["code_revision"],
            "1b9b8d3840a4bd973b3ad7919321181caf398775",
        )
        self.assertFalse(evidence["passed"])
        self.assertEqual(
            evidence["classification"],
            "input_validation_stop_before_environment_creation",
        )
        for key in (
            "environment_created",
            "scene_reset_run",
            "placement_actions_run",
            "pickup_actions_run",
            "fallback_route_run",
            "fresh_reset_replay_run",
            "memory_agents_run",
            "images_saved",
            "candidate_plan_created",
            "candidate_outcome_observed",
            "anchor_frozen",
            "floorplan301_scientific_result_available",
            "rerun_performed",
        ):
            self.assertFalse(evidence[key])
        self.assertEqual(evidence["support_query_count"], 0)
        serialized = json.dumps(evidence, sort_keys=True)
        for forbidden in (
            "selected_pose",
            "objectId",
            "target_point",
            '"x"',
            '"y"',
            '"z"',
        ):
            self.assertNotIn(forbidden, serialized)

    def test_floorplan301_v3_geometry_stop_has_no_native_trial_or_private_state(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan301_support_policy_v3_geometry_stop.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            evidence["code_revision"],
            "596e1c2db5f7ef23ab37254b886bd5c5ecdc7761",
        )
        self.assertFalse(evidence["passed"])
        self.assertEqual(
            evidence["classification"],
            "no_geometry_candidate_after_precommitted_filter",
        )
        protocol = evidence["support_query_protocol"]
        self.assertEqual(protocol["query_count"], 8)
        self.assertTrue(protocol["one_query_per_fresh_reset"])
        self.assertTrue(protocol["all_queries_succeeded"])
        self.assertFalse(protocol["query_state_reused"])
        self.assertTrue(protocol["post_query_clean_reset_before_route_and_geometry"])
        self.assertEqual(
            sum(row["coordinate_count"] for row in evidence["support_type_query_summary"]),
            3969,
        )
        self.assertEqual(
            sum(row["count"] for row in evidence["geometry_rejection_summary"]),
            3969,
        )
        self.assertEqual(evidence["accepted_geometry_candidate_count"], 0)
        self.assertEqual(evidence["candidate_trial_count"], 0)
        for key in (
            "placement_actions_run",
            "pickup_actions_run",
            "fallback_route_run",
            "fresh_reset_replay_run",
            "memory_agents_run",
            "images_saved",
            "anchor_frozen",
            "floorplan301_qualified",
            "later_scenes_started",
            "coordinates_exposed",
        ):
            self.assertFalse(evidence[key])
        serialized = json.dumps(evidence, sort_keys=True)
        for forbidden in (
            "objectId",
            "support_id",
            "selected_pose",
            "target_point",
            '"x"',
            '"y"',
            '"z"',
            "private_registry",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_candidate_queries_are_fresh_reset_isolated_before_clean_planning(self) -> None:
        module = self._qualifier_module()
        env = _FreshSupportQueryEnv()
        with tempfile.TemporaryDirectory() as temp_dir:
            plan, route, book = module._collect_precommitted_plan(
                env,
                scene="FloorPlanFixture",
                output_dir=Path(temp_dir),
                git_state={
                    "code_revision": "a" * 40,
                    "working_tree_dirty": False,
                },
                setup_actions=[],
                configuration_id="fixture",
                absolute_scan_horizon_degrees=0.0,
            )
        env.reset("FloorPlanFixture")
        self.assertEqual(len(env.query_actions), 2)
        self.assertTrue(all(action["anywhere"] is True for action in env.query_actions))
        self.assertTrue(all(count <= 1 for count in env.queries_per_reset))
        self.assertGreaterEqual(len(env.reset_scenes), 4)
        self.assertEqual(book["position"]["x"], 0.0)
        self.assertEqual(plan["target"]["before_position"]["x"], 0.0)
        self.assertEqual(plan["support_policy_version"], SUPPORT_POLICY_VERSION)
        protocol = plan["support_query_protocol"]
        self.assertTrue(protocol["one_support_query_per_fresh_reset"])
        self.assertFalse(protocol["query_state_reused_by_later_query_or_trial"])
        self.assertTrue(protocol["post_query_clean_reset_before_route_and_geometry"])
        self.assertFalse(protocol["support_policy_admission_uses_query_outcome"])
        self.assertEqual(protocol["support_query_count"], 2)
        self.assertTrue(
            all(row["fresh_reset_before_query"] for row in plan["support_query_audit"])
        )
        self.assertTrue(
            all(not row["query_state_reused"] for row in plan["support_query_audit"])
        )
        self.assertEqual(
            {row["support_type"] for row in plan["geometry"]["accepted_candidates"]},
            {"Bed", "Shelf"},
        )
        self.assertFalse(route["target_or_anchor_input_used"])

    def test_native_placement_and_replay_each_start_from_reset_setup(self) -> None:
        module = self._qualifier_module()
        initial_target = {
            **_box(
                "Book|private",
                x=0.0,
                y=1.0,
                z=0.0,
                sx=0.4,
                sy=0.08,
                sz=0.2,
                object_type="Book",
            ),
            "visible": True,
            "isMoving": False,
        }
        placed_target = {
            **_box(
                "Book|private",
                x=2.0,
                y=1.2,
                z=0.0,
                sx=0.4,
                sy=0.08,
                sz=0.2,
                object_type="Book",
                parents=["Desk|private"],
            ),
            "visible": False,
            "isMoving": False,
        }
        support = {
            **_box(
                "Desk|private",
                x=2.0,
                y=1.0,
                z=0.0,
                sx=2.0,
                sy=0.2,
                sz=1.0,
                object_type="Desk",
            ),
            "receptacle": True,
        }
        event = _Event(
            {
                "objects": [placed_target, support],
                "lastActionSuccess": True,
                "errorMessage": "",
            }
        )
        env = Mock()
        env.step.return_value = event
        reset_setup = Mock(
            return_value=({"objects": [initial_target, support]}, [])
        )
        kwargs = {
            "scene": "FloorPlanFixture",
            "target_id": "Book|private",
            "before_position": {"x": 0.0, "y": 1.0, "z": 0.0},
            "support_id": "Desk|private",
            "point": {"x": 2.0, "y": 1.2, "z": 0.0},
            "setup_actions": [],
        }
        with patch.object(module, "_reset_setup", reset_setup):
            first = module._physical_placement_trial(env, **kwargs)
            replay = module._physical_placement_trial(env, **kwargs)
        self.assertTrue(first["passed"])
        self.assertTrue(replay["passed"])
        self.assertEqual(reset_setup.call_count, 2)
        self.assertEqual(
            sum(
                call.args[0]["action"] == "PlaceObjectAtPoint"
                for call in env.step.call_args_list
            ),
            2,
        )

    def test_absolute_horizon_alignment_reaches_zero_and_restores(self) -> None:
        expected = {
            -30.0: (["LookDown"], ["LookUp"]),
            0.0: ([], []),
            30.0: (["LookUp"], ["LookDown"]),
            60.0: (["LookUp", "LookUp"], ["LookDown", "LookDown"]),
        }
        deltas = {"LookDown": 30.0, "LookUp": -30.0}
        for start, actions in expected.items():
            with self.subTest(start=start):
                setup, restore = build_absolute_horizon_alignment_actions(
                    start_horizon_degrees=start,
                    scan_horizon_degrees=0.0,
                )
                self.assertEqual((setup, restore), actions)
                aligned = start + sum(deltas[action] for action in setup)
                self.assertEqual(aligned, 0.0)
                restored = aligned + sum(deltas[action] for action in restore)
                self.assertEqual(restored, start)

    def test_absolute_horizon_alignment_rejects_unbounded_or_off_grid_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "action step"):
            build_absolute_horizon_alignment_actions(
                start_horizon_degrees=15.0,
                scan_horizon_degrees=0.0,
            )
        with self.assertRaisesRegex(ValueError, "supported range"):
            build_absolute_horizon_alignment_actions(
                start_horizon_degrees=90.0,
                scan_horizon_degrees=0.0,
            )

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

        downward_path = (
            root
            / "configs"
            / "phase5_r1_anchor_candidates_downward_v3_floorplan202.json"
        )
        downward = module._load_candidate_contract(
            downward_path, "FloorPlan202"
        )
        self.assertEqual(downward["coverage_route_action_count"], 227)
        self.assertEqual(downward["coverage_scan_horizon_degrees"], 30.0)
        self.assertEqual(
            downward["coverage_route_version"],
            "phase5-target-independent-downward-scan-v3",
        )
        absolute_path = (
            root
            / "configs"
            / "phase5_r1_anchor_candidates_absolute_v4_floorplan202.json"
        )
        absolute = module._load_candidate_contract(
            absolute_path, "FloorPlan202"
        )
        self.assertEqual(absolute["coverage_route_action_count"], 227)
        self.assertEqual(absolute["absolute_scan_horizon_degrees"], 0.0)
        self.assertEqual(
            absolute["coverage_route_version"],
            "phase5-target-independent-absolute-horizon-v4",
        )
        absolute_301 = module._load_candidate_contract(
            root
            / "configs"
            / "phase5_r1_anchor_candidates_absolute_v4_floorplan301.json",
            "FloorPlan301",
        )
        self.assertEqual(absolute_301["coverage_route_action_count"], 108)
        self.assertEqual(absolute_301["absolute_scan_horizon_degrees"], 0.0)
        self.assertEqual(
            absolute_301["coverage_route_version"],
            "phase5-target-independent-absolute-horizon-v4",
        )

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
        downward_text = (
            root
            / "configs"
            / "phase5_r1_anchor_candidates_downward_v3_floorplan202.json"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "selected_pose",
            "target_object_id",
            "target_point",
            "reachable_positions",
        ):
            self.assertNotIn(forbidden, downward_text)
        for absolute_path in sorted(
            (root / "configs").glob(
                "phase5_r1_anchor_candidates_absolute_v4_floorplan*.json"
            )
        ):
            absolute_text = absolute_path.read_text(encoding="utf-8")
            for forbidden in (
                "selected_pose",
                "target_object_id",
                "target_point",
                "reachable_positions",
            ):
                self.assertNotIn(forbidden, absolute_text)

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

    def test_axis_aware_rectangular_footprint_fits_narrow_support(self) -> None:
        target = _box(
            "Book|narrow",
            x=0,
            y=1,
            z=0,
            sx=0.52,
            sy=0.06,
            sz=0.16,
            object_type="Book",
        )
        support = _box(
            "Desk|narrow",
            x=2,
            y=1,
            z=0,
            sx=1.6,
            sy=0.1,
            sz=0.4,
            object_type="Desk",
        )
        plan = build_geometry_candidate_plan(
            target=target,
            support_queries=[
                {
                    "support": support,
                    "coordinates": [{"x": 2.0, "y": 1.1, "z": 0.0}],
                }
            ],
            all_objects=[target, support],
        )
        self.assertEqual(plan["geometry_version"], ANCHOR_GEOMETRY_VERSION)
        self.assertEqual(
            plan["qualification_version"], "phase5-anchor-qualification-v3"
        )
        self.assertEqual(
            plan["target_footprint_half_extents_meters"],
            {"x": 0.26, "z": 0.08},
        )
        self.assertEqual(len(plan["accepted_candidates"]), 1)
        self.assertEqual(plan["geometry_rejections"], [])

        rotated = dict(target)
        rotated["axisAlignedBoundingBox"] = {
            "center": {"x": 0, "y": 1, "z": 0},
            "size": {"x": 0.16, "y": 0.06, "z": 0.52},
        }
        rotated_plan = build_geometry_candidate_plan(
            target=rotated,
            support_queries=[
                {
                    "support": support,
                    "coordinates": [{"x": 2.0, "y": 1.1, "z": 0.0}],
                }
            ],
            all_objects=[rotated, support],
        )
        self.assertEqual(rotated_plan["accepted_candidates"], [])
        self.assertEqual(
            rotated_plan["geometry_rejections"][0]["reason"],
            "book_footprint_crosses_support_boundary",
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

    def test_downward_scan_route_adds_one_bounded_horizon_layer(self) -> None:
        reachable = [
            {"x": 0.0, "y": 0.9, "z": 0.0},
            {"x": 0.25, "y": 0.9, "z": 0.0},
            {"x": 0.0, "y": 0.9, "z": 0.25},
            {"x": 0.25, "y": 0.9, "z": 0.25},
        ]
        base = build_target_independent_coverage_route(
            reachable_positions=reachable,
            start_position=reachable[0],
            start_yaw=90,
            scan_spacing_steps=1,
        )
        route = build_target_independent_coverage_route(
            reachable_positions=reachable,
            start_position=reachable[0],
            start_yaw=90,
            scan_spacing_steps=1,
            scan_horizon_degrees=30.0,
        )
        self.assertEqual(
            route["route_version"],
            "phase5-target-independent-downward-scan-v3",
        )
        self.assertEqual(route["scan_horizon_degrees"], 30.0)
        self.assertTrue(route["camera_horizon_restored_at_route_end"])
        self.assertEqual(route["actions"][0]["action"], {"action": "LookDown"})
        self.assertEqual(route["actions"][-1]["action"], {"action": "LookUp"})
        self.assertEqual(len(route["actions"]), len(base["actions"]) + 2)
        self.assertEqual(
            route["actions"][1:-1],
            base["actions"],
        )
        self.assertFalse(route["target_or_anchor_input_used"])
        with self.assertRaisesRegex(ValueError, "horizon"):
            build_target_independent_coverage_route(
                reachable_positions=reachable,
                start_position=reachable[0],
                start_yaw=90,
                scan_horizon_degrees=15.0,
            )

    def test_absolute_horizon_routes_share_zero_scan_view_with_bounded_overhead(self) -> None:
        reachable = [
            {"x": 0.0, "y": 0.9, "z": 0.0},
            {"x": 0.25, "y": 0.9, "z": 0.0},
            {"x": 0.0, "y": 0.9, "z": 0.25},
            {"x": 0.25, "y": 0.9, "z": 0.25},
        ]
        base = build_target_independent_coverage_route(
            reachable_positions=reachable,
            start_position=reachable[0],
            start_yaw=90,
            scan_spacing_steps=1,
        )
        expected_overhead = {-30.0: 2, 0.0: 0, 30.0: 2, 60.0: 4}
        for start, overhead in expected_overhead.items():
            with self.subTest(start=start):
                route = build_target_independent_coverage_route(
                    reachable_positions=reachable,
                    start_position=reachable[0],
                    start_yaw=90,
                    scan_spacing_steps=1,
                    start_camera_horizon_degrees=start,
                    absolute_scan_horizon_degrees=0.0,
                )
                self.assertEqual(
                    route["route_version"],
                    "phase5-target-independent-absolute-horizon-v4",
                )
                self.assertEqual(route["absolute_scan_horizon_degrees"], 0.0)
                self.assertEqual(route["horizon_alignment_action_count"], overhead // 2)
                self.assertEqual(route["horizon_restoration_action_count"], overhead // 2)
                self.assertEqual(len(route["actions"]), len(base["actions"]) + overhead)
                self.assertLessEqual(225 + overhead, 240)
                self.assertTrue(route["camera_horizon_restored_at_route_end"])
                self.assertFalse(route["target_or_anchor_input_used"])

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

    def test_diagnostic_selector_runs_exactly_one_frozen_candidate(self) -> None:
        module = self._qualifier_module()
        candidates = [
            {"candidate_order": order, "private_point": {"x": float(order)}}
            for order in range(1, 15)
        ]
        batch = module._select_candidate_trials(
            candidates, diagnostic_candidate_order=None
        )
        self.assertEqual(len(batch), module.MAX_CANDIDATE_TRIALS)
        selected = module._select_candidate_trials(
            candidates, diagnostic_candidate_order=4
        )
        self.assertEqual([row["candidate_order"] for row in selected], [4])
        with self.assertRaisesRegex(ValueError, "positive"):
            module._select_candidate_trials(
                candidates, diagnostic_candidate_order=0
            )
        with self.assertRaisesRegex(ValueError, "exactly one"):
            module._select_candidate_trials(
                candidates, diagnostic_candidate_order=13
            )

    def test_absolute_route_precommit_summary_is_coordinate_free(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "scripts" / "precommit_phase5_absolute_route.py"
        spec = importlib.util.spec_from_file_location(
            "precommit_phase5_absolute_route", path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        route = {
            "route_version": "phase5-target-independent-absolute-horizon-v4",
            "absolute_scan_horizon_degrees": 0.0,
            "horizon_alignment_action_count": 1,
            "horizon_restoration_action_count": 1,
            "target_or_anchor_input_used": False,
            "start_node": [99, 88],
            "actions": [
                {"action": {"action": "LookDown"}},
                {"action": {"action": "RotateRight"}},
                {"action": {"action": "LookUp"}},
            ],
        }
        summary = module._coordinate_free_summary(
            scene="FloorPlanFixture",
            configuration_id="fixture_config",
            start_pose_digest="a" * 64,
            route=route,
            git_state={"code_revision": "b" * 40, "working_tree_dirty": False},
            output_dir=Path("ignored-output"),
        )
        self.assertTrue(summary["passed"])
        self.assertFalse(summary["placement_actions_run"])
        self.assertFalse(summary["memory_agents_run"])
        text = json.dumps(summary)
        for forbidden in (
            "start_node",
            "target_point",
            "anchor_id",
            "candidate_order",
            "objectId",
            "reachable_positions",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()

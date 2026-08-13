"""Offline tests for pre-qualified relocation anchor planning."""

from __future__ import annotations

import unittest
import json
import importlib.util
import inspect
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import Mock, patch

from embodied_memory_thor.phase4.contracts import PlannerRequest, audit_planner_request
from embodied_memory_thor.phase5.anchors import (
    ABSOLUTE_HORIZON_FLOAT_TOLERANCE_DEGREES,
    ABSOLUTE_HORIZON_POLICY_VERSION,
    ANCHOR_GEOMETRY_VERSION,
    ANCHOR_QUALIFICATION_VERSION,
    ANCHOR_REGISTRY_VERSION,
    BOOK_SUPPORT_TYPE_ORDER,
    BOOK_SUPPORT_TYPES,
    NATIVE_FIRST_CANDIDATE_POLICY_VERSION,
    NATIVE_CANDIDATE_POLICY_VERSION,
    SUPPORT_POLICY_VERSION,
    build_absolute_horizon_alignment_actions,
    build_geometry_candidate_plan,
    build_native_first_candidate_plan,
    build_type_balanced_native_candidate_plan,
    build_target_independent_coverage_route,
    normalize_absolute_horizon_degrees,
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
    @staticmethod
    def _route_mutation_module():
        root = Path(__file__).resolve().parents[1]
        path = root / "scripts" / "diagnose_phase5_route_mutation.py"
        spec = importlib.util.spec_from_file_location(
            "diagnose_phase5_route_mutation", path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_floorplan304_route_mutation_protocol_is_paired_and_non_recovering(self) -> None:
        root = Path(__file__).resolve().parents[1]
        protocol = json.loads(
            (
                root
                / "configs"
                / "phase5_floorplan304_route_mutation_diagnostic_v1.json"
            ).read_text(encoding="utf-8")
        )
        stop = json.loads(
            (root / protocol["source_stop_evidence"]).read_text(encoding="utf-8")
        )
        route = json.loads(
            (root / protocol["source_route_evidence"]).read_text(encoding="utf-8")
        )
        self.assertEqual(protocol["scene"], "FloorPlan304")
        self.assertEqual(protocol["route_digest"], route["route_digest"])
        self.assertEqual(protocol["route_digest"], stop["coverage_route_digest"])
        self.assertEqual(protocol["route_probe_step"], 109)
        self.assertEqual(protocol["frozen_candidate_order"], 1)
        self.assertEqual(protocol["matched_pre_route_intervention_count"], 4)
        self.assertTrue(protocol["fresh_reset_per_condition"])
        self.assertTrue(protocol["direct_route_replay_without_planner"])
        for key in (
            "support_queries_allowed",
            "new_candidate_generation_allowed",
            "memory_agents_allowed",
            "images_allowed",
            "obstacle_recovery_actions_allowed",
            "later_scenes_allowed",
        ):
            self.assertFalse(protocol[key])

    def test_route_mutation_replay_stops_at_first_failure_and_reports_type(self) -> None:
        module = self._route_mutation_module()
        route = {
            "actions": [
                {"action": {"action": "Pass"}, "phase": "one"},
                {"action": {"action": "MoveAhead"}, "phase": "two"},
                {"action": {"action": "RotateRight"}, "phase": "three"},
            ]
        }
        success = _Event(
            {"objects": [], "lastActionSuccess": True, "errorMessage": ""}
        )
        failure = _Event(
            {
                "objects": [
                    {"objectId": "LaundryHamper|private", "objectType": "LaundryHamper"}
                ],
                "lastActionSuccess": False,
                "errorMessage": "LaundryHamper|private is blocking Agent 0",
            }
        )
        env = Mock()
        env.step.side_effect = [success, failure]
        result = module.replay_route(env, route, probe_step=2)
        self.assertFalse(result["route_completed"])
        self.assertEqual(result["route_actions_attempted"], 2)
        self.assertEqual(result["first_failed_route_step"], 2)
        self.assertFalse(result["probe_step_success"])
        self.assertEqual(result["blocker_object_type"], "LaundryHamper")
        self.assertEqual(env.step.call_count, 2)

    def test_route_mutation_classification_never_runs_recovery_implicitly(self) -> None:
        module = self._route_mutation_module()
        baseline_fail = module.classify_pair(
            {"route_completed": False},
            {"route_completed": False},
            placement_success=True,
        )
        placement_fail = module.classify_pair(
            {"route_completed": True},
            {"route_completed": False},
            placement_success=True,
        )
        both_pass = module.classify_pair(
            {"route_completed": True},
            {"route_completed": True},
            placement_success=True,
        )
        invalid = module.classify_pair(
            {"route_completed": True},
            {"route_completed": True},
            placement_success=False,
        )
        self.assertEqual(
            baseline_fail["decision"], "mark_floorplan304_route_failure_and_stop"
        )
        self.assertEqual(
            placement_fail["decision"],
            "preregister_general_obstacle_recovery_and_stop",
        )
        self.assertTrue(both_pass["good_news"])
        self.assertEqual(invalid["decision"], "stop")

    def test_floorplan304_paired_diagnostic_marks_original_route_failed(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan304_route_mutation_diagnostic_v1.json"
            ).read_text(encoding="utf-8")
        )
        route = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan304_absolute_route_v4_1_precommit.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(evidence["diagnostic_valid"])
        self.assertFalse(evidence["good_news"])
        self.assertEqual(
            evidence["classification"], "original_route_intrinsically_blocked"
        )
        self.assertEqual(
            evidence["decision"], "mark_floorplan304_route_failure_and_stop"
        )
        self.assertEqual(evidence["route_digest"], route["route_digest"])
        self.assertEqual(evidence["route_action_count"], route["route_action_count"])
        self.assertTrue(evidence["placement"]["placement_success"])
        for condition in ("baseline", "placement"):
            row = evidence[condition]
            self.assertFalse(row["route_completed"])
            self.assertEqual(row["route_actions_attempted"], 109)
            self.assertEqual(row["first_failed_route_step"], 109)
            self.assertEqual(row["failed_action_name"], "MoveAhead")
            self.assertEqual(row["failed_route_phase"], "coverage_move")
            self.assertEqual(row["blocker_object_type"], "LaundryHamper")
        self.assertTrue(evidence["same_failure_step_action_phase_and_blocker"])
        self.assertFalse(evidence["book_placement_caused_route_failure"])
        self.assertTrue(evidence["route_execution_failure_present_without_book_placement"])
        self.assertFalse(evidence["obstacle_recovery_policy_selected"])
        for key in (
            "support_queries_run",
            "new_candidates_generated",
            "planner_run",
            "memory_agents_run",
            "images_saved",
            "obstacle_recovery_actions_run",
            "anchor_frozen",
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
            '"private_registry":',
        ):
            self.assertNotIn(forbidden, serialized)

    @staticmethod
    def _baseline_route_module():
        root = Path(__file__).resolve().parents[1]
        path = root / "scripts" / "execute_phase5_baseline_route.py"
        spec = importlib.util.spec_from_file_location(
            "execute_phase5_baseline_route", path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_route_execution_gate_freezes_floorplan304_and_floorplan305_order(self) -> None:
        root = Path(__file__).resolve().parents[1]
        gate = json.loads(
            (
                root / "configs" / "phase5_r1_route_execution_gate_v1.json"
            ).read_text(encoding="utf-8")
        )
        ineligible = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan304_route_execution_ineligible_v1.json"
            ).read_text(encoding="utf-8")
        )
        source = json.loads(
            (root / ineligible["source_execution_diagnostic"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(gate["qualified_scene_count_before_gate"], 3)
        self.assertEqual(
            gate["remaining_route_construction_eligible_scene_order"][0],
            "FloorPlan305",
        )
        self.assertEqual(ineligible["classification"], "route_execution_ineligible")
        self.assertTrue(ineligible["route_construction_eligible"])
        self.assertFalse(ineligible["route_execution_eligible"])
        self.assertTrue(ineligible["scene_skip_allowed"])
        self.assertEqual(
            ineligible["first_failed_route_step"],
            source["baseline"]["first_failed_route_step"],
        )
        self.assertEqual(ineligible["blocker_object_type"], "LaundryHamper")
        self.assertFalse(gate["support_queries_allowed_during_route_gates"])
        self.assertFalse(gate["placement_allowed_during_route_gates"])
        self.assertFalse(gate["obstacle_recovery_policy_enabled"])
        self.assertFalse(gate["memory_agents_allowed"])
        self.assertFalse(gate["images_allowed"])

    def test_baseline_route_execution_classification_distinguishes_skip_from_stop(self) -> None:
        module = self._baseline_route_module()
        passed = module.classify_execution(
            {"route_completed": True},
            precondition_passed=True,
            reset_restoration_passed=True,
            fatal_error="",
        )
        blocked = module.classify_execution(
            {"route_completed": False},
            precondition_passed=True,
            reset_restoration_passed=True,
            fatal_error="",
        )
        invalid = module.classify_execution(
            {"route_completed": False},
            precondition_passed=True,
            reset_restoration_passed=False,
            fatal_error="",
        )
        fatal = module.classify_execution(
            {"route_completed": False},
            precondition_passed=True,
            reset_restoration_passed=True,
            fatal_error="RuntimeError: fixture",
        )
        self.assertTrue(passed["passed"])
        self.assertEqual(passed["classification"], "baseline_route_execution_passed")
        self.assertFalse(blocked["passed"])
        self.assertEqual(blocked["classification"], "route_execution_ineligible")
        self.assertTrue(blocked["scene_skip_allowed"])
        for row in (invalid, fatal):
            self.assertEqual(row["classification"], "baseline_route_execution_invalid")
            self.assertFalse(row["scene_skip_allowed"])

    def test_native_contract_baseline_gate_rejects_missing_or_mismatched_pass(self) -> None:
        module = self._qualifier_module()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as raw:
            temp_root = Path(raw)
            evidence_path = temp_root / "baseline.json"
            relative = evidence_path.relative_to(Path(__file__).resolve().parents[1])
            contract = {
                "baseline_route_execution_required": True,
                "baseline_route_execution_evidence": str(relative),
                "coverage_route_digest": "route-digest",
                "coverage_route_action_count": 7,
            }
            evidence = {
                "scene": "FloorPlanFixture",
                "passed": True,
                "classification": "baseline_route_execution_passed",
                "route_digest": "route-digest",
                "route_action_count": 7,
                "reset_restoration_passed": True,
                "placement_actions_run": False,
                "memory_agents_run": False,
            }
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            module._validate_baseline_execution_gate(
                contract, scene="FloorPlanFixture"
            )
            evidence["route_action_count"] = 8
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                module._validate_baseline_execution_gate(
                    contract, scene="FloorPlanFixture"
                )
            contract.pop("baseline_route_execution_evidence")
            with self.assertRaisesRegex(ValueError, "is required"):
                module._validate_baseline_execution_gate(
                    contract, scene="FloorPlanFixture"
                )

    def test_floorplan305_route_and_baseline_pass_gate_native_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        module = self._qualifier_module()
        contract_path = (
            root
            / "configs"
            / "phase5_r1_anchor_candidates_absolute_v4_floorplan305.json"
        )
        contract = module._load_candidate_contract(contract_path, "FloorPlan305")
        route = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan305_absolute_route_v4_precommit.json"
            ).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan305_baseline_route_execution_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(route["passed"])
        self.assertEqual(route["route_action_count"], 115)
        self.assertTrue(baseline["passed"])
        self.assertEqual(baseline["route_actions_attempted"], 115)
        self.assertTrue(baseline["route_completed"])
        self.assertTrue(baseline["reset_restoration_passed"])
        self.assertEqual(contract["coverage_route_digest"], route["route_digest"])
        self.assertEqual(contract["coverage_route_digest"], baseline["route_digest"])
        self.assertEqual(
            contract["coverage_route_action_count"], route["route_action_count"]
        )
        self.assertTrue(contract["baseline_route_execution_required"])
        module._validate_baseline_execution_gate(contract, scene="FloorPlan305")
        for evidence in (route, baseline):
            serialized = json.dumps(evidence, sort_keys=True)
            for forbidden in (
                "objectId",
                "support_id",
                "selected_pose",
                "target_point",
                '"x"',
                '"y"',
                '"z"',
            ):
                self.assertNotIn(forbidden, serialized)

    def test_floorplan305_native_v7_result_qualifies_after_execution_gate(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan305_native_qualification_v7.json"
            ).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan305_baseline_route_execution_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(baseline["passed"])
        self.assertTrue(evidence["baseline_route_execution_passed"])
        self.assertTrue(evidence["passed"])
        self.assertTrue(evidence["anchor_frozen"])
        self.assertEqual(evidence["candidate_trial_count"], 1)
        self.assertEqual(evidence["selected_support_type"], "Bed")
        self.assertGreaterEqual(evidence["target_move_distance_xz_meters"], 0.5)
        self.assertTrue(evidence["old_view_invisible"])
        self.assertTrue(evidence["three_sample_stability_passed"])
        self.assertTrue(evidence["expected_support_relation_passed"])
        self.assertEqual(evidence["post_placement_non_support_overlap_count"], 0)
        self.assertTrue(evidence["common_fallback_passed"])
        self.assertEqual(evidence["fallback_discovery_step"], 38)
        self.assertEqual(evidence["fallback_pickup_step"], 39)
        self.assertEqual(evidence["fallback_failed_action_count"], 0)
        self.assertTrue(evidence["fresh_reset_replay_passed"])
        self.assertTrue(evidence["reset_restoration_passed"])
        self.assertEqual(evidence["coverage_route_digest"], baseline["route_digest"])
        self.assertEqual(evidence["qualified_r1_scene_count_after_run"], 4)
        for key in (
            "query_state_reused",
            "force_action_used",
            "book_rotation_action_used",
            "memory_agents_run",
            "images_saved",
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
        ):
            self.assertNotIn(forbidden, serialized)

    def test_floorplan306_route_and_baseline_pass_gate_native_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        module = self._qualifier_module()
        contract = module._load_candidate_contract(
            root
            / "configs"
            / "phase5_r1_anchor_candidates_absolute_v4_floorplan306.json",
            "FloorPlan306",
        )
        route = json.loads(
            (
                root / "docs" / "evidence"
                / "phase5_floorplan306_absolute_route_v4_precommit.json"
            ).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (
                root / "docs" / "evidence"
                / "phase5_floorplan306_baseline_route_execution_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(route["passed"])
        self.assertTrue(baseline["passed"])
        self.assertEqual(route["route_action_count"], 150)
        self.assertEqual(baseline["route_actions_attempted"], 150)
        self.assertTrue(baseline["route_completed"])
        self.assertTrue(baseline["reset_restoration_passed"])
        self.assertEqual(contract["coverage_route_digest"], route["route_digest"])
        self.assertEqual(contract["coverage_route_digest"], baseline["route_digest"])
        self.assertEqual(contract["coverage_route_action_count"], 150)
        module._validate_baseline_execution_gate(contract, scene="FloorPlan306")
        for evidence in (route, baseline):
            serialized = json.dumps(evidence, sort_keys=True)
            for forbidden in (
                "objectId", "support_id", "selected_pose", "target_point",
                '"x"', '"y"', '"z"',
            ):
                self.assertNotIn(forbidden, serialized)

    def test_floorplan306_native_v7_result_is_fifth_qualified_scene(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root / "docs" / "evidence"
                / "phase5_floorplan306_native_qualification_v7.json"
            ).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (
                root / "docs" / "evidence"
                / "phase5_floorplan306_baseline_route_execution_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(baseline["passed"])
        self.assertTrue(evidence["passed"])
        self.assertTrue(evidence["anchor_frozen"])
        self.assertEqual(evidence["candidate_trial_count"], 1)
        self.assertEqual(evidence["selected_support_type"], "Bed")
        self.assertGreaterEqual(evidence["target_move_distance_xz_meters"], 0.5)
        self.assertTrue(evidence["old_view_invisible"])
        self.assertTrue(evidence["three_sample_stability_passed"])
        self.assertTrue(evidence["expected_support_relation_passed"])
        self.assertEqual(evidence["post_placement_non_support_overlap_count"], 0)
        self.assertTrue(evidence["common_fallback_passed"])
        self.assertEqual(evidence["fallback_discovery_step"], 94)
        self.assertEqual(evidence["fallback_pickup_step"], 95)
        self.assertEqual(evidence["fallback_failed_action_count"], 0)
        self.assertTrue(evidence["fresh_reset_replay_passed"])
        self.assertTrue(evidence["reset_restoration_passed"])
        self.assertEqual(evidence["qualified_r1_scene_count_after_run"], 5)
        self.assertEqual(evidence["coverage_route_digest"], baseline["route_digest"])
        for key in (
            "query_state_reused", "force_action_used", "book_rotation_action_used",
            "memory_agents_run", "images_saved", "later_scenes_started",
            "coordinates_exposed",
        ):
            self.assertFalse(evidence[key])

    def test_floorplan307_route_and_baseline_pass_gate_native_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        module = self._qualifier_module()
        contract = module._load_candidate_contract(
            root / "configs" / "phase5_r1_anchor_candidates_absolute_v4_floorplan307.json",
            "FloorPlan307",
        )
        route = json.loads((root / "docs" / "evidence" / "phase5_floorplan307_absolute_route_v4_precommit.json").read_text(encoding="utf-8"))
        baseline = json.loads((root / "docs" / "evidence" / "phase5_floorplan307_baseline_route_execution_v1.json").read_text(encoding="utf-8"))
        self.assertTrue(route["passed"])
        self.assertTrue(baseline["passed"])
        self.assertEqual(route["route_action_count"], 113)
        self.assertEqual(baseline["route_actions_attempted"], 113)
        self.assertTrue(baseline["route_completed"])
        self.assertTrue(baseline["reset_restoration_passed"])
        self.assertEqual(contract["coverage_route_digest"], route["route_digest"])
        self.assertEqual(contract["coverage_route_digest"], baseline["route_digest"])
        module._validate_baseline_execution_gate(contract, scene="FloorPlan307")
        for evidence in (route, baseline):
            serialized = json.dumps(evidence, sort_keys=True)
            for forbidden in ("objectId", "support_id", "selected_pose", "target_point", '"x"', '"y"', '"z"'):
                self.assertNotIn(forbidden, serialized)

    def test_floorplan307_native_v7_result_completes_six_scene_target(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads((root / "docs" / "evidence" / "phase5_floorplan307_native_qualification_v7.json").read_text(encoding="utf-8"))
        baseline = json.loads((root / "docs" / "evidence" / "phase5_floorplan307_baseline_route_execution_v1.json").read_text(encoding="utf-8"))
        self.assertTrue(baseline["passed"])
        self.assertTrue(evidence["passed"])
        self.assertTrue(evidence["anchor_frozen"])
        self.assertEqual(evidence["candidate_trial_count"], 1)
        self.assertEqual(evidence["selected_support_type"], "Bed")
        self.assertGreaterEqual(evidence["target_move_distance_xz_meters"], 0.5)
        self.assertTrue(evidence["old_view_invisible"])
        self.assertTrue(evidence["three_sample_stability_passed"])
        self.assertTrue(evidence["expected_support_relation_passed"])
        self.assertEqual(evidence["post_placement_non_support_overlap_count"], 0)
        self.assertTrue(evidence["common_fallback_passed"])
        self.assertEqual(evidence["fallback_discovery_step"], 39)
        self.assertEqual(evidence["fallback_pickup_step"], 40)
        self.assertEqual(evidence["fallback_failed_action_count"], 0)
        self.assertTrue(evidence["fresh_reset_replay_passed"])
        self.assertTrue(evidence["reset_restoration_passed"])
        self.assertEqual(evidence["qualified_r1_scene_count_after_run"], 6)
        self.assertEqual(
            evidence["qualified_r1_scenes_after_run"],
            ["FloorPlan202", "FloorPlan302", "FloorPlan303", "FloorPlan305", "FloorPlan306", "FloorPlan307"],
        )
        for key in ("query_state_reused", "memory_agents_run", "images_saved", "later_scenes_started", "coordinates_exposed"):
            self.assertFalse(evidence[key])

    def test_frozen_six_anchor_manifest_is_private_safe_and_source_complete(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "configs" / "phase5_r1_frozen_anchor_set_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["target_anchor_count"], 6)
        self.assertEqual(
            [row["scene"] for row in manifest["scenes"]],
            ["FloorPlan202", "FloorPlan302", "FloorPlan303", "FloorPlan305", "FloorPlan306", "FloorPlan307"],
        )
        self.assertEqual(
            [row["scene"] for row in manifest["excluded_scenes"]],
            ["FloorPlan301", "FloorPlan304"],
        )
        self.assertTrue(manifest["scene_expansion_complete"])
        self.assertFalse(manifest["next_scene_started"])
        self.assertFalse(manifest["planner_visible"])
        self.assertFalse(manifest["coordinates_public"])
        serialized = json.dumps(manifest, sort_keys=True)
        for forbidden in ("objectId", "support_id", "selected_pose", "target_point", '"x"', '"y"', '"z"'):
            self.assertNotIn(forbidden, serialized)

    def test_private_six_anchor_merge_verifies_sources_without_leaking_publicly(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "scripts" / "freeze_phase5_r1_anchor_set.py"
        spec = importlib.util.spec_from_file_location("freeze_phase5_r1_anchor_set", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        manifest = json.loads((root / "configs" / "phase5_r1_frozen_anchor_set_v1.json").read_text(encoding="utf-8"))
        frozen = module.build_frozen_anchor_set(manifest, root=root)
        self.assertEqual(frozen["anchor_count"], 6)
        self.assertEqual(len(frozen["anchors"]), 6)
        self.assertEqual(len(set(frozen["scenes"])), 6)
        self.assertFalse(frozen["planner_visible"])
        self.assertFalse(frozen["included_in_planner_metrics"])
        self.assertEqual(len(frozen["private_anchor_set_digest"]), 64)

    def test_frozen_six_anchor_public_result_matches_private_merge_digest(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads((root / "docs" / "evidence" / "phase5_r1_frozen_six_anchor_set_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["anchor_count"], 6)
        self.assertEqual(evidence["scenes"], ["FloorPlan202", "FloorPlan302", "FloorPlan303", "FloorPlan305", "FloorPlan306", "FloorPlan307"])
        self.assertEqual(evidence["private_anchor_set_digest"], "423cf8ef98d73b56d836edbda83563cf4ebdc0604063e1ccf9530f876f781d92")
        for key in ("source_registry_scene_match_passed", "source_registry_digest_match_passed", "one_unique_anchor_per_scene_passed", "public_qualification_evidence_passed", "private_registry_written", "private_registry_git_ignored", "scene_expansion_complete"):
            self.assertTrue(evidence[key])
        for key in ("planner_visible", "coordinates_exposed", "memory_agents_run", "images_saved", "floorplan308_started"):
            self.assertFalse(evidence[key])
        serialized = json.dumps(evidence, sort_keys=True)
        for forbidden in ("objectId", "support_id", "selected_pose", "target_point", '"x"', '"y"', '"z"'):
            self.assertNotIn(forbidden, serialized)

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
            ANCHOR_QUALIFICATION_VERSION, "phase5-anchor-qualification-v7"
        )
        self.assertEqual(
            ANCHOR_REGISTRY_VERSION, "phase5-private-anchor-registry-v7"
        )
        self.assertTrue(policy["one_support_query_per_fresh_reset"])
        self.assertFalse(policy["query_state_reused_by_later_query_or_trial"])
        self.assertFalse(policy["placement_outcomes_used_for_support_type_admission"])
        self.assertFalse(policy["formal_episode_dynamic_spawn_query_allowed"])
        self.assertTrue(policy["formal_episode_uses_frozen_anchor_only"])
        self.assertTrue(policy["native_anchor_qualification_is_acceptance_authority"])
        self.assertEqual(
            policy["candidate_policy_version"], NATIVE_CANDIDATE_POLICY_VERSION
        )
        self.assertIn(
            "phase5_r1_support_census_paired_causal_v4.json",
            policy["retained_failed_evidence"],
        )

    def test_native_qualification_v4_freezes_full_batch_and_action_boundaries(self) -> None:
        root = Path(__file__).resolve().parents[1]
        protocol = json.loads(
            (root / "configs" / "phase5_r1_native_qualification_v4.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(protocol["scene"], "FloorPlan301")
        self.assertEqual(
            protocol["candidate_policy_version"],
            NATIVE_FIRST_CANDIDATE_POLICY_VERSION,
        )
        self.assertEqual(
            protocol["qualification_version"], "phase5-anchor-qualification-v4"
        )
        self.assertEqual(
            protocol["private_registry_version"],
            "phase5-private-anchor-registry-v4",
        )
        self.assertEqual(protocol["maximum_native_candidate_trials"], 12)
        self.assertTrue(protocol["candidate_order_frozen_before_native_outcomes"])
        self.assertTrue(protocol["placement_trial_fresh_reset"])
        self.assertTrue(protocol["fresh_reset_replay_required"])
        self.assertFalse(protocol["force_action_allowed"])
        self.assertFalse(protocol["book_rotation_action_allowed"])
        self.assertFalse(protocol["memory_agents_allowed"])
        self.assertFalse(protocol["later_scenes_allowed"])
        self.assertIn("retain every failure", protocol["batch_rule"])

    def test_native_qualification_v5_freezes_type_balanced_batch(self) -> None:
        root = Path(__file__).resolve().parents[1]
        protocol = json.loads(
            (root / "configs" / "phase5_r1_native_qualification_v5.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(protocol["scene"], "FloorPlan301")
        self.assertEqual(
            protocol["qualification_version"], "phase5-anchor-qualification-v5"
        )
        self.assertEqual(
            protocol["private_registry_version"],
            "phase5-private-anchor-registry-v5",
        )
        self.assertEqual(
            protocol["candidate_policy_version"], NATIVE_CANDIDATE_POLICY_VERSION
        )
        self.assertEqual(protocol["maximum_native_candidate_trials"], 12)
        self.assertTrue(protocol["candidate_order_frozen_before_native_outcomes"])
        self.assertFalse(protocol["prior_v4_outcomes_used_to_select_candidates"])
        self.assertFalse(protocol["v4_cohort_extended_or_pooled"])
        self.assertEqual(
            protocol["support_type_order"], list(BOOK_SUPPORT_TYPE_ORDER)
        )
        self.assertTrue(protocol["placement_trial_fresh_reset"])
        self.assertFalse(protocol["force_action_allowed"])
        self.assertFalse(protocol["book_rotation_action_allowed"])
        self.assertFalse(protocol["memory_agents_allowed"])
        self.assertFalse(protocol["later_scenes_allowed"])

    def test_floorplan302_v6_requires_valid_predecessor_and_route_precommit(self) -> None:
        root = Path(__file__).resolve().parents[1]
        protocol = json.loads(
            (
                root
                / "configs"
                / "phase5_r1_native_qualification_v6_floorplan302.json"
            ).read_text(encoding="utf-8")
        )
        predecessor = json.loads(
            (root / protocol["predecessor_public_evidence"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(protocol["scene"], "FloorPlan302")
        self.assertEqual(protocol["declared_scene_predecessor"], "FloorPlan301")
        self.assertEqual(
            protocol["qualification_version"], "phase5-anchor-qualification-v6"
        )
        self.assertEqual(
            protocol["private_registry_version"],
            "phase5-private-anchor-registry-v6",
        )
        self.assertEqual(
            predecessor["classification"],
            protocol["predecessor_required_classification"],
        )
        self.assertEqual(
            predecessor["candidate_trial_count"],
            protocol["predecessor_required_trial_count"],
        )
        self.assertEqual(
            predecessor["reset_restoration_failure_count"],
            protocol["predecessor_required_reset_restoration_failure_count"],
        )
        self.assertTrue(protocol["route_only_precommit_required_before_placement"])
        self.assertFalse(protocol["runtime_or_integrity_failure_allows_scene_skip"])
        self.assertFalse(protocol["prior_scene_outcomes_used_to_select_candidates"])
        self.assertEqual(protocol["maximum_native_candidate_trials"], 12)
        self.assertFalse(protocol["force_action_allowed"])
        self.assertFalse(protocol["book_rotation_action_allowed"])
        self.assertFalse(protocol["memory_agents_allowed"])
        self.assertFalse(protocol["later_scenes_allowed_by_this_contract"])

    def test_floorplan303_v7_follows_audited_pass_in_declared_order(self) -> None:
        root = Path(__file__).resolve().parents[1]
        protocol = json.loads(
            (
                root
                / "configs"
                / "phase5_r1_native_qualification_v7_floorplan303.json"
            ).read_text(encoding="utf-8")
        )
        predecessor = json.loads(
            (root / protocol["predecessor_public_evidence"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(protocol["scene"], "FloorPlan303")
        self.assertEqual(protocol["declared_scene_predecessor"], "FloorPlan302")
        self.assertEqual(protocol["qualification_version"], ANCHOR_QUALIFICATION_VERSION)
        self.assertEqual(protocol["private_registry_version"], ANCHOR_REGISTRY_VERSION)
        self.assertEqual(protocol["qualified_scene_count_before_run"], 2)
        self.assertEqual(
            protocol["qualified_scenes_before_run"],
            ["FloorPlan202", "FloorPlan302"],
        )
        self.assertEqual(protocol["failed_scenes_before_run"], ["FloorPlan301"])
        self.assertEqual(
            predecessor["passed"], protocol["predecessor_required_passed"]
        )
        self.assertEqual(
            predecessor["anchor_frozen"],
            protocol["predecessor_required_anchor_frozen"],
        )
        self.assertEqual(
            predecessor["reset_restoration_passed"],
            protocol["predecessor_required_reset_restoration_passed"],
        )
        self.assertTrue(protocol["route_only_precommit_required_before_placement"])
        self.assertFalse(protocol["prior_scene_outcomes_used_to_select_candidates"])
        self.assertEqual(protocol["maximum_native_candidate_trials"], 12)
        self.assertFalse(protocol["force_action_allowed"])
        self.assertFalse(protocol["book_rotation_action_allowed"])
        self.assertFalse(protocol["memory_agents_allowed"])
        self.assertFalse(protocol["later_scenes_allowed_by_this_contract"])

    def test_floorplan304_v7_follows_audited_pass_in_declared_order(self) -> None:
        root = Path(__file__).resolve().parents[1]
        protocol = json.loads(
            (
                root
                / "configs"
                / "phase5_r1_native_qualification_v7_floorplan304.json"
            ).read_text(encoding="utf-8")
        )
        predecessor = json.loads(
            (root / protocol["predecessor_public_evidence"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(protocol["scene"], "FloorPlan304")
        self.assertEqual(protocol["declared_scene_predecessor"], "FloorPlan303")
        self.assertEqual(protocol["qualification_version"], ANCHOR_QUALIFICATION_VERSION)
        self.assertEqual(protocol["private_registry_version"], ANCHOR_REGISTRY_VERSION)
        self.assertEqual(protocol["qualified_scene_count_before_run"], 3)
        self.assertEqual(
            protocol["qualified_scenes_before_run"],
            ["FloorPlan202", "FloorPlan302", "FloorPlan303"],
        )
        self.assertEqual(protocol["failed_scenes_before_run"], ["FloorPlan301"])
        self.assertEqual(
            predecessor["passed"], protocol["predecessor_required_passed"]
        )
        self.assertEqual(
            predecessor["anchor_frozen"],
            protocol["predecessor_required_anchor_frozen"],
        )
        self.assertEqual(
            predecessor["reset_restoration_passed"],
            protocol["predecessor_required_reset_restoration_passed"],
        )
        self.assertEqual(
            protocol["horizon_policy_version"], ABSOLUTE_HORIZON_POLICY_VERSION
        )
        self.assertTrue(protocol["route_only_precommit_required_before_placement"])
        self.assertFalse(protocol["prior_scene_outcomes_used_to_select_candidates"])
        self.assertEqual(protocol["maximum_native_candidate_trials"], 12)
        self.assertFalse(protocol["force_action_allowed"])
        self.assertFalse(protocol["book_rotation_action_allowed"])
        self.assertFalse(protocol["memory_agents_allowed"])
        self.assertFalse(protocol["images_allowed"])
        self.assertFalse(protocol["later_scenes_allowed_by_this_contract"])

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
            '"private_registry":',
        ):
            self.assertNotIn(forbidden, serialized)

    def test_floorplan301_native_v4_result_exhausts_frozen_prefix_without_expansion(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan301_native_qualification_v4.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            evidence["code_revision"],
            "548c7ceb55e621949933a0b90eff5eef31e8d0cc",
        )
        self.assertFalse(evidence["passed"])
        self.assertEqual(
            evidence["classification"],
            "native_candidate_prefix_exhausted_without_anchor",
        )
        self.assertEqual(evidence["candidate_trial_count"], 12)
        self.assertEqual(evidence["frozen_native_candidate_trial_limit"], 12)
        self.assertEqual(evidence["native_placement_attempt_count"], 12)
        self.assertEqual(evidence["native_placement_success_count"], 0)
        self.assertEqual(
            evidence["candidate_support_type_summary"],
            [{"support_type": "Shelf", "candidate_trial_count": 12}],
        )
        self.assertEqual(evidence["fallback_route_run_count"], 0)
        self.assertEqual(evidence["fresh_reset_replay_run_count"], 0)
        self.assertEqual(evidence["reset_restoration_pass_count"], 12)
        self.assertEqual(evidence["reset_restoration_failure_count"], 0)
        for key in (
            "query_state_reused",
            "force_action_used",
            "book_rotation_action_used",
            "memory_agents_run",
            "images_saved",
            "anchor_frozen",
            "full_floorplan301_qualification_passed",
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
            '"private_registry":',
        ):
            self.assertNotIn(forbidden, serialized)

    def test_floorplan301_native_v5_result_is_balanced_and_private_safe(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan301_native_qualification_v5.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            evidence["code_revision"],
            "d3e8ca14aa02671a70b5eec894bbffdc99437a6e",
        )
        self.assertFalse(evidence["passed"])
        self.assertEqual(
            evidence["classification"],
            "balanced_native_candidate_prefix_exhausted_without_anchor",
        )
        self.assertTrue(evidence["independent_from_v4_cohort"])
        self.assertFalse(evidence["v4_outcomes_used_to_select_candidates"])
        self.assertEqual(evidence["candidate_trial_count"], 12)
        self.assertEqual(evidence["frozen_native_candidate_trial_limit"], 12)
        self.assertEqual(
            evidence["candidate_support_type_summary"],
            [
                {"support_type": "Desk", "candidate_trial_count": 4},
                {"support_type": "Dresser", "candidate_trial_count": 4},
                {"support_type": "Shelf", "candidate_trial_count": 4},
            ],
        )
        self.assertEqual(evidence["native_placement_attempt_count"], 12)
        self.assertEqual(evidence["native_placement_success_count"], 0)
        self.assertEqual(
            sum(row["count"] for row in evidence["native_error_category_summary"]),
            12,
        )
        self.assertEqual(evidence["fallback_route_run_count"], 0)
        self.assertEqual(evidence["fresh_reset_replay_run_count"], 0)
        self.assertEqual(evidence["reset_restoration_pass_count"], 12)
        self.assertEqual(evidence["reset_restoration_failure_count"], 0)
        for key in (
            "query_state_reused",
            "force_action_used",
            "book_rotation_action_used",
            "memory_agents_run",
            "images_saved",
            "anchor_frozen",
            "full_floorplan301_qualification_passed",
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
            '"private_registry":',
        ):
            self.assertNotIn(forbidden, serialized)

    def test_floorplan302_native_v6_result_fully_qualifies_without_leakage(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan302_native_qualification_v6.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            evidence["code_revision"],
            "90a1ec73a4c26691d62c6eb6bc00edd522e36bff",
        )
        self.assertTrue(evidence["passed"])
        self.assertEqual(
            evidence["classification"],
            "first_balanced_native_candidate_fully_qualified",
        )
        self.assertEqual(evidence["candidate_trial_count"], 1)
        self.assertEqual(evidence["selected_candidate_order"], 1)
        self.assertEqual(evidence["selected_support_type"], "Bed")
        self.assertEqual(evidence["native_placement_success_count"], 1)
        self.assertGreaterEqual(evidence["target_move_distance_xz_meters"], 0.5)
        for key in (
            "old_view_invisible",
            "three_sample_stability_passed",
            "expected_support_relation_passed",
            "common_fallback_passed",
            "fresh_reset_replay_passed",
            "reset_restoration_passed",
            "anchor_frozen",
        ):
            self.assertTrue(evidence[key])
        self.assertEqual(evidence["post_placement_non_support_overlap_count"], 0)
        self.assertEqual(evidence["fallback_discovery_step"], 20)
        self.assertEqual(evidence["fallback_pickup_step"], 21)
        self.assertEqual(evidence["fallback_failed_action_count"], 0)
        for key in (
            "query_state_reused",
            "force_action_used",
            "book_rotation_action_used",
            "memory_agents_run",
            "images_saved",
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
            '"private_registry":',
        ):
            self.assertNotIn(forbidden, serialized)

    def test_floorplan303_native_v7_result_fully_qualifies_after_route_gate(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan303_native_qualification_v7.json"
            ).read_text(encoding="utf-8")
        )
        route_evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan303_absolute_route_v4_1_precommit.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(route_evidence["passed"])
        self.assertTrue(evidence["passed"])
        self.assertEqual(
            evidence["coverage_route_digest"], route_evidence["route_digest"]
        )
        self.assertEqual(
            evidence["coverage_route_action_count"],
            route_evidence["route_action_count"],
        )
        self.assertEqual(
            evidence["classification"],
            "first_balanced_native_candidate_fully_qualified",
        )
        self.assertEqual(evidence["candidate_trial_count"], 1)
        self.assertEqual(evidence["selected_candidate_order"], 1)
        self.assertEqual(evidence["selected_support_type"], "Bed")
        self.assertEqual(evidence["native_placement_success_count"], 1)
        self.assertGreaterEqual(evidence["target_move_distance_xz_meters"], 0.5)
        for key in (
            "old_view_invisible",
            "three_sample_stability_passed",
            "expected_support_relation_passed",
            "common_fallback_passed",
            "fresh_reset_replay_passed",
            "reset_restoration_passed",
            "anchor_frozen",
        ):
            self.assertTrue(evidence[key])
        self.assertEqual(evidence["post_placement_non_support_overlap_count"], 0)
        self.assertEqual(evidence["fallback_discovery_step"], 68)
        self.assertEqual(evidence["fallback_pickup_step"], 69)
        self.assertEqual(evidence["fallback_failed_action_count"], 0)
        self.assertEqual(evidence["qualified_r1_scene_count_after_run"], 3)
        self.assertEqual(
            evidence["qualified_r1_scenes_after_run"],
            ["FloorPlan202", "FloorPlan302", "FloorPlan303"],
        )
        for key in (
            "query_state_reused",
            "force_action_used",
            "book_rotation_action_used",
            "memory_agents_run",
            "images_saved",
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
            '"private_registry":',
        ):
            self.assertNotIn(forbidden, serialized)

    def test_floorplan304_native_v7_result_stops_on_fallback_route_failure(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan304_native_qualification_v7.json"
            ).read_text(encoding="utf-8")
        )
        route_evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan304_absolute_route_v4_1_precommit.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(route_evidence["passed"])
        self.assertFalse(evidence["passed"])
        self.assertEqual(evidence["fatal_error"], "")
        self.assertTrue(evidence["batch_process_completed"])
        self.assertFalse(evidence["scene_skip_as_clean_exhaustion_allowed"])
        self.assertEqual(
            evidence["classification"],
            "native_batch_completed_without_anchor_with_fallback_route_execution_failure",
        )
        self.assertEqual(
            evidence["coverage_route_digest"], route_evidence["route_digest"]
        )
        self.assertEqual(
            evidence["coverage_route_action_count"],
            route_evidence["route_action_count"],
        )
        self.assertEqual(evidence["candidate_trial_count"], 12)
        self.assertEqual(
            evidence["candidate_support_type_summary"],
            [
                {"support_type": "Bed", "candidate_trial_count": 6},
                {"support_type": "Shelf", "candidate_trial_count": 6},
            ],
        )
        self.assertEqual(evidence["native_placement_success_count"], 6)
        self.assertEqual(evidence["physical_qa_pass_count"], 6)
        self.assertEqual(evidence["common_fallback_run_count"], 6)
        self.assertEqual(evidence["common_fallback_pass_count"], 0)
        self.assertEqual(
            evidence["common_fallback_failure_summary"][0]["failed_route_step"],
            109,
        )
        self.assertEqual(evidence["fresh_reset_replay_run_count"], 0)
        self.assertEqual(evidence["reset_restoration_pass_count"], 12)
        self.assertEqual(evidence["reset_restoration_failure_count"], 0)
        self.assertEqual(evidence["qualified_r1_scene_count_after_run"], 3)
        for key in (
            "force_action_used",
            "book_rotation_action_used",
            "memory_agents_run",
            "images_saved",
            "anchor_frozen",
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
            '"private_registry":',
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

    def test_route_v4_1_normalizes_real_thor_boundary_drift_only(self) -> None:
        observed = 60.00001525878906
        self.assertEqual(
            normalize_absolute_horizon_degrees(observed),
            60.0,
        )
        self.assertEqual(
            ABSOLUTE_HORIZON_POLICY_VERSION,
            "phase5-absolute-horizon-tolerance-v4.1",
        )
        self.assertEqual(ABSOLUTE_HORIZON_FLOAT_TOLERANCE_DEGREES, 0.001)
        setup, restore = build_absolute_horizon_alignment_actions(
            start_horizon_degrees=observed,
            scan_horizon_degrees=0.0,
        )
        self.assertEqual(setup, ["LookUp", "LookUp"])
        self.assertEqual(restore, ["LookDown", "LookDown"])
        for invalid in (60.5, 61.0):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "supported range"):
                    normalize_absolute_horizon_degrees(invalid)

    def test_route_v4_1_preserves_exact_grid_digests_and_private_input_boundary(self) -> None:
        reachable = [
            {"x": 0.0, "y": 0.9, "z": 0.0},
            {"x": 0.25, "y": 0.9, "z": 0.0},
            {"x": 0.0, "y": 0.9, "z": 0.25},
            {"x": 0.25, "y": 0.9, "z": 0.25},
        ]
        expected = {
            -30.0: "46ec17fb52f6b4ae1f507659de5cc6e69725784b9d364b9fa7da3caa133d6baa",
            0.0: "678a308131abc031977f12490776d784bcfb73ac34220f095fc0d17ae2d491b9",
        }
        for horizon, expected_digest in expected.items():
            with self.subTest(horizon=horizon):
                route = build_target_independent_coverage_route(
                    reachable_positions=reachable,
                    start_position=reachable[0],
                    start_yaw=90,
                    scan_spacing_steps=1,
                    start_camera_horizon_degrees=horizon,
                    absolute_scan_horizon_degrees=0.0,
                )
                self.assertEqual(
                    route["route_version"],
                    "phase5-target-independent-absolute-horizon-v4",
                )
                self.assertEqual(stable_digest(route), expected_digest)
                self.assertFalse(route["target_or_anchor_input_used"])
                self.assertNotIn("horizon_normalization_applied", route)

        normalized = build_target_independent_coverage_route(
            reachable_positions=reachable,
            start_position=reachable[0],
            start_yaw=90,
            scan_spacing_steps=1,
            start_camera_horizon_degrees=60.00001525878906,
            absolute_scan_horizon_degrees=0.0,
        )
        self.assertEqual(
            normalized["route_version"],
            "phase5-target-independent-absolute-horizon-v4.1",
        )
        self.assertEqual(normalized["initial_camera_horizon_degrees"], 60.0)
        self.assertTrue(normalized["horizon_normalization_applied"])
        self.assertFalse(normalized["target_or_anchor_input_used"])

        parameter_names = set(
            inspect.signature(build_target_independent_coverage_route).parameters
        )
        self.assertTrue(
            {"target", "anchor", "support", "candidate", "target_point"}.isdisjoint(
                parameter_names
            )
        )

        root = Path(__file__).resolve().parents[1]
        public_digests = {
            "FloorPlan202": "cb82c0057aa6d9a89d9493745c3ccc8db2047ebfae78e9fb65af022495777cae",
            "FloorPlan302": "8844fb4f2424b3b143ffcf2de8c58f249ab5ba35206289a0e11d4b60f1e9400a",
        }
        for scene, expected_digest in public_digests.items():
            evidence_path = (
                root
                / "docs"
                / "evidence"
                / (
                    "phase5_floorplan202_absolute_route_v4_anchor_qualification.json"
                    if scene == "FloorPlan202"
                    else "phase5_floorplan302_absolute_route_v4_precommit.json"
                )
            )
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            digest_key = (
                "coverage_route_digest" if scene == "FloorPlan202" else "route_digest"
            )
            self.assertEqual(evidence[digest_key], expected_digest)

        request = PlannerRequest(
            task_name="thor_book_reacquire_k2",
            instruction="Reacquire and pick up the Book.",
            task_stage="reacquire_book",
            step=1,
            max_steps=240,
            observation={
                "scene_name": "FloorPlanFixture",
                "agent": {
                    "position": {"x": 0.0, "y": 0.9, "z": 0.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "cameraHorizon": 60.0,
                },
                "objects": [],
                "inventory": [],
                "last_action": "",
                "last_action_success": True,
                "last_action_error": "",
            },
            allowed_actions=("LookUp", "LookDown", "RotateRight"),
            shared_search={
                "action": {"action": "LookUp"},
                "action_index": 0,
                "action_sequence_digest": "a" * 64,
                "phase": "coverage",
                "policy": "frozen_target_independent_route",
                "route_id": "route-v4-1-fixture",
            },
        )
        audit = audit_planner_request(request)
        self.assertTrue(audit.passed, audit.violations)

        def keys(value: Any) -> set[str]:
            if isinstance(value, Mapping):
                return set(map(str, value)) | set().union(
                    *(keys(item) for item in value.values())
                )
            if isinstance(value, (list, tuple)):
                return set().union(*(keys(item) for item in value))
            return set()

        planner_keys = keys(request.snapshot(include_digest=False))
        self.assertTrue(
            {
                "target_point",
                "target_position",
                "anchor_id",
                "support_id",
                "candidate_point",
                "reachable_positions",
                "route_coordinates",
            }.isdisjoint(planner_keys)
        )

    def test_route_v4_1_protocol_freezes_tolerance_and_compatibility_claims(self) -> None:
        root = Path(__file__).resolve().parents[1]
        protocol = json.loads(
            (
                root / "configs" / "phase5_route_v4_1_horizon_tolerance.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            protocol["policy_version"], ABSOLUTE_HORIZON_POLICY_VERSION
        )
        self.assertEqual(
            protocol["tolerance_degrees"],
            ABSOLUTE_HORIZON_FLOAT_TOLERANCE_DEGREES,
        )
        self.assertEqual(protocol["accepted_observed_value_degrees"], 60.00001525878906)
        self.assertEqual(protocol["normalized_value_degrees"], 60.0)
        self.assertEqual(protocol["must_reject_values_degrees"], [60.5, 61.0])
        self.assertTrue(protocol["exact_grid_route_serialization_unchanged"])
        self.assertFalse(protocol["planner_input_schema_changed"])
        self.assertFalse(protocol["target_anchor_support_or_coordinate_input_added"])
        self.assertFalse(protocol["native_qualification_allowed_before_route_pass"])
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
        absolute_302 = module._load_candidate_contract(
            root
            / "configs"
            / "phase5_r1_anchor_candidates_absolute_v4_floorplan302.json",
            "FloorPlan302",
        )
        self.assertEqual(absolute_302["coverage_route_action_count"], 61)
        self.assertEqual(absolute_302["absolute_scan_horizon_degrees"], 0.0)
        self.assertEqual(
            absolute_302["coverage_route_version"],
            "phase5-target-independent-absolute-horizon-v4",
        )
        self.assertEqual(
            absolute_302["coverage_route_digest"],
            "8844fb4f2424b3b143ffcf2de8c58f249ab5ba35206289a0e11d4b60f1e9400a",
        )
        absolute_303 = module._load_candidate_contract(
            root
            / "configs"
            / "phase5_r1_anchor_candidates_absolute_v4_1_floorplan303.json",
            "FloorPlan303",
        )
        self.assertEqual(absolute_303["coverage_route_action_count"], 100)
        self.assertEqual(absolute_303["absolute_scan_horizon_degrees"], 0.0)
        self.assertEqual(
            absolute_303["coverage_route_version"],
            "phase5-target-independent-absolute-horizon-v4.1",
        )
        self.assertEqual(
            absolute_303["coverage_route_digest"],
            "5d4de455b78ab05f17038cb7b5cf4dbc63c736d4b0c0fdf40e733545319c4254",
        )
        absolute_304 = module._load_candidate_contract(
            root
            / "configs"
            / "phase5_r1_anchor_candidates_absolute_v4_1_floorplan304.json",
            "FloorPlan304",
        )
        self.assertEqual(absolute_304["coverage_route_action_count"], 127)
        self.assertEqual(absolute_304["absolute_scan_horizon_degrees"], 0.0)
        self.assertEqual(
            absolute_304["coverage_route_version"],
            "phase5-target-independent-absolute-horizon-v4.1",
        )
        self.assertEqual(
            absolute_304["coverage_route_digest"],
            "6892b381c8957171367a3513d278ddbb5300b039dae50ed998a684bed0a3679b",
        )

    def test_floorplan304_route_v4_1_public_pass_is_bounded_and_private_safe(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan304_absolute_route_v4_1_precommit.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(evidence["passed"])
        self.assertEqual(
            evidence["route_version"],
            "phase5-target-independent-absolute-horizon-v4.1",
        )
        self.assertEqual(
            evidence["horizon_policy_version"],
            ABSOLUTE_HORIZON_POLICY_VERSION,
        )
        self.assertEqual(evidence["route_action_count"], 127)
        self.assertLessEqual(evidence["route_action_count"], 240)
        self.assertEqual(evidence["observed_start_horizon_degrees"], 30.000003814697266)
        self.assertEqual(evidence["normalized_start_horizon_degrees"], 30.0)
        self.assertTrue(evidence["horizon_normalization_applied"])
        self.assertEqual(evidence["horizon_alignment_action_count"], 1)
        self.assertEqual(evidence["horizon_restoration_action_count"], 1)
        for key in (
            "target_or_anchor_input_used",
            "support_queries_run",
            "placement_actions_run",
            "memory_agents_run",
            "images_saved",
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
        ):
            self.assertNotIn(forbidden, serialized)

    def test_floorplan303_route_v4_1_public_pass_is_bounded_and_private_safe(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan303_absolute_route_v4_1_precommit.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(evidence["passed"])
        self.assertEqual(
            evidence["route_version"],
            "phase5-target-independent-absolute-horizon-v4.1",
        )
        self.assertEqual(
            evidence["horizon_policy_version"],
            ABSOLUTE_HORIZON_POLICY_VERSION,
        )
        self.assertEqual(evidence["route_action_count"], 100)
        self.assertLessEqual(evidence["route_action_count"], 240)
        self.assertEqual(evidence["observed_start_horizon_degrees"], 60.00001525878906)
        self.assertEqual(evidence["normalized_start_horizon_degrees"], 60.0)
        self.assertTrue(evidence["horizon_normalization_applied"])
        self.assertEqual(evidence["horizon_alignment_action_count"], 2)
        self.assertEqual(evidence["horizon_restoration_action_count"], 2)
        for key in (
            "target_or_anchor_input_used",
            "support_queries_run",
            "placement_actions_run",
            "memory_agents_run",
            "images_saved",
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
        ):
            self.assertNotIn(forbidden, serialized)

    def test_floorplan302_route_v4_public_precommit_is_read_only_and_private_safe(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan302_absolute_route_v4_precommit.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(evidence["passed"])
        self.assertEqual(evidence["route_action_count"], 61)
        self.assertLessEqual(evidence["route_action_count"], 240)
        self.assertEqual(evidence["absolute_scan_horizon_degrees"], 0.0)
        for key in (
            "target_or_anchor_input_used",
            "support_queries_run",
            "placement_actions_run",
            "memory_agents_run",
            "images_saved",
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
        ):
            self.assertNotIn(forbidden, serialized)

    def test_floorplan303_route_v4_stop_is_float_boundary_only_and_private_safe(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "docs"
                / "evidence"
                / "phase5_floorplan303_route_v4_float_boundary_stop.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(evidence["passed"])
        self.assertEqual(
            evidence["classification"],
            "camera_horizon_float_boundary_rejection",
        )
        self.assertEqual(evidence["requested_start_horizon_degrees"], 60.0)
        self.assertGreater(evidence["observed_start_horizon_degrees"], 60.0)
        self.assertLess(evidence["observed_boundary_excess_degrees"], 0.001)
        self.assertTrue(evidence["teleport_probe_succeeded"])
        for key in (
            "route_constructed",
            "support_queries_run",
            "placement_actions_run",
            "memory_agents_run",
            "images_saved",
            "anchor_frozen",
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
        ):
            self.assertNotIn(forbidden, serialized)

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

    def test_native_first_plan_keeps_geometry_risks_for_native_qa(self) -> None:
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
        args = {
            "target": target,
            "support_queries": [
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
            "all_objects": [target, support, pan],
        }
        first = build_native_first_candidate_plan(**args)
        second = build_native_first_candidate_plan(**args)
        self.assertEqual(first, second)
        self.assertEqual(stable_digest(first), stable_digest(second))
        self.assertEqual(
            first["candidate_policy_version"],
            NATIVE_FIRST_CANDIDATE_POLICY_VERSION,
        )
        self.assertTrue(first["native_placement_is_acceptance_authority"])
        self.assertFalse(first["boundary_prediction_is_hard_rejection"])
        self.assertFalse(first["obstacle_prediction_is_hard_rejection"])
        self.assertEqual(len(first["accepted_candidates"]), 4)
        self.assertEqual(first["geometry_rejections"], [])
        self.assertTrue(first["accepted_candidates"][0]["advisory_predicted_clear"])
        self.assertTrue(
            all(
                row["native_trial_required_for_acceptance"]
                for row in first["accepted_candidates"]
            )
        )
        self.assertTrue(
            any(
                row["advisory_boundary_passed"] is False
                for row in first["accepted_candidates"]
            )
        )
        self.assertTrue(
            any(
                row["advisory_obstacle_overlap_count"] > 0
                for row in first["accepted_candidates"]
            )
        )
        self.assertNotIn("placement_success", str(first))

    def test_type_balanced_native_plan_round_robins_present_semantic_types(self) -> None:
        target = _box(
            "Book|1", x=0, y=1, z=0, sx=0.5, sy=0.06, sz=0.2,
            object_type="Book",
        )
        supports = [
            _box(
                "Shelf|1", x=6, y=1, z=0, sx=2, sy=0.1, sz=2,
                object_type="Shelf",
            ),
            _box(
                "Dresser|1", x=4, y=1, z=0, sx=2, sy=0.1, sz=2,
                object_type="Dresser",
            ),
            _box(
                "Desk|1", x=2, y=1, z=0, sx=2, sy=0.1, sz=2,
                object_type="Desk",
            ),
        ]
        queries = [
            {
                "support": support,
                "coordinates": [
                    {"x": support["position"]["x"], "y": 1.1, "z": -0.1},
                    {"x": support["position"]["x"], "y": 1.1, "z": 0.1},
                ],
            }
            for support in supports
        ]
        args = {
            "target": target,
            "support_queries": queries,
            "all_objects": [target, *supports],
        }
        first = build_type_balanced_native_candidate_plan(**args)
        second = build_type_balanced_native_candidate_plan(**args)
        self.assertEqual(first, second)
        self.assertEqual(stable_digest(first), stable_digest(second))
        self.assertEqual(first["qualification_version"], ANCHOR_QUALIFICATION_VERSION)
        self.assertEqual(
            first["candidate_policy_version"], NATIVE_CANDIDATE_POLICY_VERSION
        )
        self.assertEqual(
            first["source_within_type_policy_version"],
            NATIVE_FIRST_CANDIDATE_POLICY_VERSION,
        )
        self.assertFalse(first["support_type_balancing_uses_native_outcomes"])
        self.assertEqual(first["present_support_types"], ["Desk", "Dresser", "Shelf"])
        self.assertEqual(
            [row["support_type"] for row in first["accepted_candidates"]],
            ["Desk", "Dresser", "Shelf", "Desk", "Dresser", "Shelf"],
        )
        self.assertEqual(
            [row["within_type_order"] for row in first["accepted_candidates"]],
            [1, 1, 1, 2, 2, 2],
        )
        self.assertEqual(
            [row["candidate_order"] for row in first["accepted_candidates"]],
            list(range(1, 7)),
        )
        self.assertNotIn("placement_success", str(first))

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
            plan["qualification_version"], "phase5-anchor-qualification-v4"
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

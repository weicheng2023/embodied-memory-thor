"""Offline tests for discrete memory navigation and bounded fallback escape."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from embodied_memory_thor.phase4.contracts import (
    PlannerDecision,
    PlannerRequest,
    audit_planner_request,
)
from embodied_memory_thor.phase4.planners import (
    THOR_CUP_COFFEE_ACTIONS,
    ThorBookReacquirePlanner,
)
from embodied_memory_thor.phase4.runner import ThorEpisodeConfig, ThorEpisodeRunner
from embodied_memory_thor.phase5.memory_navigation import (
    MEMORY_NAVIGATION_NONPROGRESS_ACTION_BUDGET,
    MEMORY_NAVIGATION_POLICY_VERSION,
    MemoryNavigationGuard,
    quantize_yaw_to_action_grid,
)
from embodied_memory_thor.phase5.search import FrozenSearchRoute
from tests.test_phase5_ordered_task import _CupCoffeeThorEnv


def _observation(*, x: float, z: float, yaw: float) -> dict:
    return {
        "scene_name": "FloorPlanFixture",
        "agent": {
            "position": {"x": x, "y": 0.9, "z": z},
            "rotation": {"x": 0.0, "y": yaw, "z": 0.0},
            "cameraHorizon": 0.0,
            "isStanding": True,
        },
        "objects": [],
        "inventory": [],
        "last_action": "Pass",
        "last_action_success": True,
        "last_action_error": "",
    }


def _record() -> dict:
    return {
        "record_id": "object:Cup|visible-history",
        "object_id": "Cup|visible-history",
        "object_type": "Cup",
        "last_seen_agent_position": {"x": -0.75, "y": 0.9, "z": -1.25},
        "last_seen_agent_rotation": {"x": 0.0, "y": 90.0, "z": 0.0},
        "last_seen_camera_horizon": 0.0,
        "last_seen_step": 0,
        "source_observation_id": "observation:0",
        "observed_visible": True,
        "status": "fresh",
    }


def _request(*, x: float, z: float, yaw: float) -> PlannerRequest:
    return PlannerRequest(
        task_name="thor_cup_after_coffee_subgoal",
        instruction="Reacquire Cup.",
        task_stage="reacquire_cup",
        step=9,
        max_steps=140,
        observation=_observation(x=x, z=z, yaw=yaw),
        allowed_actions=THOR_CUP_COFFEE_ACTIONS,
        retrieved_memory=(_record(),),
    )


def _route(route_id: str, codes: str, *, role: str, goal_used: bool) -> FrozenSearchRoute:
    names = {
        "D": "LookDown",
        "F": "MoveAhead",
        "L": "RotateLeft",
        "R": "RotateRight",
        "U": "LookUp",
    }
    actions = [{"action": names[code]} for code in codes]
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
        action_codes=codes,
        route_role=role,
        qualification_goal_input_used=goal_used,
        target_or_anchor_input_used=goal_used,
    )


class Phase5MemoryNavigationTests(unittest.TestCase):
    def test_continuous_bearings_quantize_deterministically_to_90_degree_grid(self) -> None:
        expected = {
            0.0: 0.0,
            44.9: 0.0,
            45.0: 90.0,
            134.9: 90.0,
            135.0: 180.0,
            225.0: 270.0,
            315.0: 0.0,
            326.309932: 0.0,
            -33.690068: 0.0,
        }
        for bearing, heading in expected.items():
            with self.subTest(bearing=bearing):
                self.assertEqual(quantize_yaw_to_action_grid(bearing), heading)
        with self.assertRaisesRegex(ValueError, "divide 360"):
            quantize_yaw_to_action_grid(10.0, step_degrees=70.0)

    def test_real_failure_geometry_rotates_once_then_translates(self) -> None:
        planner = ThorBookReacquirePlanner(memory_rotation_step_degrees=90.0)
        first = planner.plan(_request(x=-0.25, z=-2.0, yaw=90.0))
        self.assertEqual(first.action, {"action": "RotateLeft"})
        self.assertEqual(first.reason_code, "return_to_last_seen_position_heading")
        second = planner.plan(_request(x=-0.25, z=-2.0, yaw=0.0))
        self.assertEqual(second.action, {"action": "MoveAhead"})
        self.assertEqual(second.reason_code, "return_to_last_seen_position")
        self.assertTrue(first.memory_guided)
        self.assertTrue(second.memory_guided)

    def test_guard_suppresses_after_bounded_nonprogress_then_recovers_on_visibility(self) -> None:
        guard = MemoryNavigationGuard()
        record = _record()
        stationary = _observation(x=-0.25, z=-2.0, yaw=90.0)
        suppressed = ()
        for _ in range(MEMORY_NAVIGATION_NONPROGRESS_ACTION_BUDGET):
            suppressed = guard.record_result(
                memory_guided=True,
                record_ids=(record["record_id"],),
                observation_before=stationary,
                observation_after=stationary,
            )
        self.assertEqual(suppressed, (record["record_id"],))
        self.assertEqual(guard.filter_retrieved((record,)), ())
        self.assertEqual(guard.escape_count, 1)
        self.assertEqual(
            guard.refresh_visible_records((record["record_id"],)),
            (record["record_id"],),
        )
        self.assertEqual(guard.filter_retrieved((record,)), (record,))
        self.assertEqual(guard.recovery_count, 1)

    def test_translation_resets_nonprogress_without_suppressing_memory(self) -> None:
        guard = MemoryNavigationGuard()
        record_id = _record()["record_id"]
        before = _observation(x=0.0, z=0.0, yaw=0.0)
        rotated = _observation(x=0.0, z=0.0, yaw=90.0)
        moved = _observation(x=0.0, z=0.25, yaw=90.0)
        guard.record_result(
            memory_guided=True,
            record_ids=(record_id,),
            observation_before=before,
            observation_after=rotated,
        )
        self.assertEqual(guard.nonprogress_streak, 1)
        self.assertEqual(
            guard.record_result(
                memory_guided=True,
                record_ids=(record_id,),
                observation_before=rotated,
                observation_after=moved,
            ),
            (),
        )
        self.assertEqual(guard.nonprogress_streak, 0)
        self.assertEqual(guard.suppressed_record_ids, set())

    def test_policy_uses_only_planner_safe_history_and_adds_no_hidden_input(self) -> None:
        request = _request(x=-0.25, z=-2.0, yaw=90.0)
        audit = audit_planner_request(request)
        self.assertTrue(audit.passed, audit.violations)
        serialized = str(request.snapshot())
        for forbidden in (
            "reachable_positions",
            "anchor",
            "candidate_order",
            "destination_pose",
            "support_id",
        ):
            self.assertNotIn(forbidden, serialized)
        snapshot = MemoryNavigationGuard().snapshot()
        self.assertEqual(snapshot["policy"], MEMORY_NAVIGATION_POLICY_VERSION)
        self.assertNotIn("suppressed_record_ids", snapshot)

    def test_runner_switches_to_same_frozen_fallback_after_bounded_nonprogress(self) -> None:
        class _ForcedNonprogressPlanner:
            name = "forced_nonprogress_memory_fixture"

            def __init__(self) -> None:
                self.reference = ThorBookReacquirePlanner()

            def plan(self, request: PlannerRequest) -> PlannerDecision:
                if request.task_stage == "reacquire_cup" and request.retrieved_memory:
                    record_id = str(request.retrieved_memory[0]["record_id"])
                    return PlannerDecision(
                        action={"action": "Pass"},
                        target_object_type="Cup",
                        memory_guided=True,
                        memory_record_ids=(record_id,),
                        reason_code="forced_nonprogress_memory_fixture",
                        rationale="Exercise the bounded memory-to-fallback guard.",
                        planner_name=self.name,
                    )
                return self.reference.plan(request)

        subgoal = _route(
            "FloorPlan1_R2_subgoal_guard_fixture",
            "R",
            role="task_subgoal_navigation",
            goal_used=True,
        )
        fallback = _route(
            "FloorPlan1_R2_fallback_guard_fixture",
            "RRR",
            role="target_independent_fallback",
            goal_used=False,
        )
        with tempfile.TemporaryDirectory() as temporary_dir:
            output_dir = Path(temporary_dir) / "bounded_escape"
            summary = ThorEpisodeRunner(
                ThorEpisodeConfig(
                    task="thor_cup_after_coffee_subgoal",
                    scene="FloorPlan1",
                    planner="deterministic",
                    memory="object_memory",
                    subgoal_route_id=subgoal.route_id,
                    search_route_id=fallback.route_id,
                    max_steps=14,
                    output_dir=output_dir,
                    save_frames=False,
                    trace_html=False,
                ),
                env=_CupCoffeeThorEnv(),
                planner=_ForcedNonprogressPlanner(),
                subgoal_route=subgoal,
                search_route=fallback,
            ).run()
        self.assertTrue(summary["success"], summary["failure_reason"])
        self.assertTrue(summary["information_boundary_passed"])
        self.assertEqual(summary["memory_navigation"]["escape_count"], 1)
        self.assertEqual(summary["memory_navigation"]["recovery_count"], 1)
        self.assertEqual(summary["memory_navigation"]["suppressed_record_count"], 0)
        self.assertEqual(summary["shared_search_coverage_action_count"], 3)
        self.assertEqual(summary["shared_search_alignment_action_count"], 0)

    def test_runner_backtracks_memory_departure_before_shared_fallback(self) -> None:
        class _MovingCupCoffeeThorEnv(_CupCoffeeThorEnv):
            def step(self, action_dict: dict) -> object:
                action = str(action_dict.get("action", ""))
                if action == "MoveAhead":
                    self.z += 0.25
                    self.last_event = self._event(
                        last_action=action, success=True
                    )
                    return self.last_event
                if action == "MoveBack":
                    self.z -= 0.25
                    self.last_event = self._event(
                        last_action=action, success=True
                    )
                    return self.last_event
                return super().step(action_dict)

        class _MoveThenStallPlanner:
            name = "move_then_stall_memory_fixture"

            def __init__(self) -> None:
                self.reference = ThorBookReacquirePlanner()
                self.memory_action_count = 0

            def plan(self, request: PlannerRequest) -> PlannerDecision:
                if request.task_stage == "reacquire_cup" and request.retrieved_memory:
                    record_id = str(request.retrieved_memory[0]["record_id"])
                    self.memory_action_count += 1
                    action = (
                        {"action": "MoveAhead"}
                        if self.memory_action_count == 1
                        else {"action": "Pass"}
                    )
                    return PlannerDecision(
                        action=action,
                        target_object_type="Cup",
                        memory_guided=True,
                        memory_record_ids=(record_id,),
                        reason_code="move_then_stall_memory_fixture",
                        rationale=(
                            "Exercise route-entry recovery after a successful "
                            "memory-guided departure."
                        ),
                        planner_name=self.name,
                    )
                return self.reference.plan(request)

        subgoal = _route(
            "FloorPlan1_R2_subgoal_entry_recovery_fixture",
            "R",
            role="task_subgoal_navigation",
            goal_used=True,
        )
        fallback = _route(
            "FloorPlan1_R2_fallback_entry_recovery_fixture",
            "RRR",
            role="target_independent_fallback",
            goal_used=False,
        )
        with tempfile.TemporaryDirectory() as temporary_dir:
            output_dir = Path(temporary_dir) / "entry_recovery"
            summary = ThorEpisodeRunner(
                ThorEpisodeConfig(
                    task="thor_cup_after_coffee_subgoal",
                    scene="FloorPlan1",
                    planner="deterministic",
                    memory="object_memory",
                    subgoal_route_id=subgoal.route_id,
                    search_route_id=fallback.route_id,
                    max_steps=14,
                    output_dir=output_dir,
                    save_frames=False,
                    trace_html=False,
                ),
                env=_MovingCupCoffeeThorEnv(),
                planner=_MoveThenStallPlanner(),
                subgoal_route=subgoal,
                search_route=fallback,
            ).run()
            trace = [
                json.loads(line)
                for line in (output_dir / "episode.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
        self.assertTrue(summary["success"], summary["failure_reason"])
        self.assertTrue(summary["information_boundary_passed"])
        self.assertEqual(summary["memory_navigation"]["escape_count"], 1)
        self.assertEqual(summary["shared_search_entry_departure_action_count"], 1)
        self.assertEqual(summary["shared_search_entry_recovery_action_count"], 1)
        self.assertEqual(
            summary["shared_search_entry_recovery_pending_action_count"], 0
        )
        self.assertEqual(
            summary["shared_search_entry_recovery_record_failure_count"], 0
        )
        self.assertEqual(summary["shared_search_coverage_action_count"], 3)
        recovery = [
            row for row in trace
            if row["planner_decision"]["reason_code"]
            == "shared_search_route_entry_recovery"
        ]
        self.assertEqual(len(recovery), 1)
        self.assertEqual(recovery[0]["planner_decision"]["action"], {"action": "MoveBack"})
        ordinary = json.dumps(recovery, sort_keys=True)
        for forbidden in ("target_point", "anchor_id", "support_id"):
            self.assertNotIn(forbidden, ordinary)


if __name__ == "__main__":
    unittest.main()

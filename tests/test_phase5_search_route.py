"""Acceptance tests for the public matched Phase 5 coverage route."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from embodied_memory_thor.phase4.contracts import (
    PlannerRequest,
    audit_planner_request,
)
from embodied_memory_thor.phase4.planners import (
    THOR_BOOK_ACTIONS,
    ThorBookReacquirePlanner,
    validate_planner_decision,
)
from embodied_memory_thor.phase4.runner import ThorEpisodeConfig, ThorEpisodeRunner
from embodied_memory_thor.phase5.search import (
    FrozenSearchRoute,
    FrozenSearchRouteState,
    SHARED_SEARCH_ENTRY_RECOVERY_ACTION_LIMIT,
    SHARED_SEARCH_ENTRY_RECOVERY_POLICY_VERSION,
    SearchRouteError,
    load_frozen_search_route,
)
from tests.test_phase5_stale_intervention import (
    _FrozenBookRelocation,
    _RelocatableBookThorEnv,
)


ROUTE_ID = "FloorPlan1_R1_fixed_start_001_coverage_v2"
ROUTE_DIGEST = "00f638bd2ae07bac41ad176fcd221ad94f0e2241440946ce34a0f894a4a51ba8"
SOURCE_DIGEST = "5e3c77a3bf865c8c5015a4283eb3475061aa98660d4ba1d5f4dcb6c040c32576"


def _pose_observation(
    *,
    yaw: float,
    x: float = -1.0,
    z: float = 1.25,
    horizon: float = 0.0,
) -> dict[str, Any]:
    return {
        "scene_name": "FloorPlan1",
        "agent": {
            "position": {"x": x, "y": 0.9, "z": z},
            "rotation": {"x": 0.0, "y": yaw, "z": 0.0},
            "cameraHorizon": horizon,
            "isStanding": True,
        },
        "objects": [],
        "inventory": [],
        "last_action": "Pass",
        "last_action_success": True,
        "last_action_error": "",
    }


class Phase5SearchRouteTests(unittest.TestCase):
    def test_downward_horizon_codes_are_coordinate_free_and_valid(self) -> None:
        actions = [
            {"action": "LookDown"},
            {"action": "RotateRight"},
            {"action": "LookUp"},
        ]
        digest = hashlib.sha256(
            json.dumps(
                actions,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()
        route = FrozenSearchRoute(
            route_id="offline_downward_scan",
            task="thor_book_reacquire_k2",
            scene="OfflineFixture",
            source_qualification_route_digest="a" * 64,
            action_sequence_digest=digest,
            action_codes="DRU",
        )
        route.validate()
        self.assertEqual(route.actions, actions)

    def test_absolute_horizon_route_is_shared_by_all_variants_without_private_input(self) -> None:
        actions = [
            {"action": "LookDown"},
            {"action": "RotateRight"},
            {"action": "LookUp"},
        ]
        digest = hashlib.sha256(
            json.dumps(
                actions,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()
        route = FrozenSearchRoute(
            route_id="offline_absolute_horizon_v4",
            task="thor_book_reacquire_k2",
            scene="OfflineFixture",
            source_qualification_route_digest="b" * 64,
            action_sequence_digest=digest,
            action_codes="DRU",
        )
        sequences: dict[str, list[dict[str, Any]]] = {}
        for variant in ("no_memory", "short_memory_k2", "object_memory"):
            observation = _pose_observation(yaw=90.0, horizon=-30.0)
            state = FrozenSearchRouteState(
                route,
                initial_observation=observation,
            )
            sequence = []
            for index, expected in enumerate(actions):
                directive = state.next_directive(observation)
                request = PlannerRequest(
                    task_name="thor_book_reacquire_k2",
                    instruction="Reacquire and pick up the Book.",
                    task_stage="reacquire_book",
                    step=index + 4,
                    max_steps=20,
                    observation=observation,
                    allowed_actions=THOR_BOOK_ACTIONS,
                    retrieved_memory=(),
                    shared_search=directive,
                )
                audit = audit_planner_request(request)
                self.assertTrue(audit.passed, (variant, audit.violations))
                decision = ThorBookReacquirePlanner().plan(request)
                self.assertEqual(decision.action, expected)
                self.assertTrue(validate_planner_decision(decision, request)[0])
                state.record_result(
                    directive,
                    action=decision.action,
                    success=True,
                )
                sequence.append(decision.action)
                ordinary = json.dumps(request.snapshot(include_digest=False))
                for forbidden in (
                    "target_point",
                    "anchor_id",
                    "candidate_order",
                    "private_registry",
                    "relocation_destination",
                ):
                    self.assertNotIn(forbidden, ordinary)
            sequences[variant] = sequence
        self.assertEqual(sequences["no_memory"], sequences["short_memory_k2"])
        self.assertEqual(sequences["no_memory"], sequences["object_memory"])

    def test_exact_qualified_action_sequence_is_coordinate_free(self) -> None:
        route = load_frozen_search_route(ROUTE_ID)
        self.assertEqual(route.action_count, 210)
        self.assertEqual(route.action_sequence_digest, ROUTE_DIGEST)
        self.assertEqual(route.source_qualification_route_digest, SOURCE_DIGEST)
        self.assertFalse(route.target_or_anchor_input_used)
        self.assertEqual(set(route.action_codes), {"F", "L", "R"})

        public_text = json.dumps(route.public_reference(), sort_keys=True)
        registry_text = (
            Path(__file__).resolve().parents[1]
            / "configs"
            / "phase5_search_routes.json"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "anchor_id",
            "target_point",
            "coordinates",
            "objectId",
            "support_id",
            "destination",
        ):
            self.assertNotIn(forbidden, public_text)
            self.assertNotIn(forbidden, registry_text)

    def test_route_entry_alignment_uses_only_planner_safe_agent_pose(self) -> None:
        route = load_frozen_search_route(ROUTE_ID)
        state = FrozenSearchRouteState(
            route,
            initial_observation=_pose_observation(yaw=90.0),
        )
        alignment = state.next_directive(_pose_observation(yaw=180.0))
        self.assertEqual(alignment["phase"], "route_entry_alignment")
        self.assertEqual(alignment["action"], {"action": "RotateLeft"})
        state.record_result(
            alignment,
            action={"action": "RotateLeft"},
            success=True,
        )
        coverage = state.next_directive(_pose_observation(yaw=90.0))
        self.assertEqual(coverage["phase"], "coverage")
        self.assertEqual(coverage["action_index"], 0)
        self.assertEqual(coverage["action"], route.actions[0])
        self.assertEqual(state.coverage_cursor, 0)

        with self.assertRaisesRegex(SearchRouteError, "position mismatch"):
            state.next_directive(_pose_observation(yaw=90.0, x=-0.5))

        stalled = FrozenSearchRouteState(
            route,
            initial_observation=_pose_observation(yaw=90.0),
        )
        stalled_alignment = stalled.next_directive(_pose_observation(yaw=180.0))
        stalled.record_result(
            stalled_alignment,
            action={"action": "RotateLeft"},
            success=True,
        )
        with self.assertRaisesRegex(SearchRouteError, "did not converge"):
            stalled.next_directive(_pose_observation(yaw=180.0))

    def test_planner_must_execute_shared_search_directive_exactly(self) -> None:
        route = load_frozen_search_route(ROUTE_ID)
        state = FrozenSearchRouteState(
            route,
            initial_observation=_pose_observation(yaw=90.0),
        )
        directive = state.next_directive(_pose_observation(yaw=90.0))
        request = PlannerRequest(
            task_name="thor_book_reacquire_k2",
            instruction="Reacquire and pick up the Book.",
            task_stage="reacquire_book",
            step=4,
            max_steps=240,
            observation=_pose_observation(yaw=90.0),
            allowed_actions=THOR_BOOK_ACTIONS,
            retrieved_memory=(),
            shared_search=directive,
        )
        audit = audit_planner_request(request)
        self.assertTrue(audit.passed, audit.violations)
        decision = ThorBookReacquirePlanner().plan(request)
        self.assertEqual(decision.action, directive["action"])
        self.assertEqual(decision.reason_code, "shared_search_coverage")
        self.assertFalse(decision.memory_guided)
        self.assertTrue(validate_planner_decision(decision, request)[0])

    def test_entry_recovery_reverses_pose_actions_without_private_input(self) -> None:
        route = load_frozen_search_route(ROUTE_ID)
        state = FrozenSearchRouteState(
            route,
            initial_observation=_pose_observation(yaw=90.0),
        )
        departures = (
            {"action": "RotateRight"},
            {"action": "MoveAhead"},
            {"action": "LookDown"},
        )
        for action in departures:
            state.record_entry_departure_action(action=action, success=True)

        observations = (
            _pose_observation(yaw=180.0, z=1.5, horizon=30.0),
            _pose_observation(yaw=180.0, z=1.5, horizon=0.0),
            _pose_observation(yaw=180.0, z=1.25, horizon=0.0),
        )
        expected = (
            {"action": "LookUp"},
            {"action": "MoveBack"},
            {"action": "RotateLeft"},
        )
        for index, (observation, action) in enumerate(zip(observations, expected)):
            directive = state.next_directive(observation)
            self.assertEqual(directive["phase"], "route_entry_recovery")
            self.assertEqual(directive["action_index"], index)
            self.assertEqual(directive["action"], action)
            request = PlannerRequest(
                task_name="thor_book_reacquire_k2",
                instruction="Reacquire and pick up the Book.",
                task_stage="reacquire_book",
                step=index + 4,
                max_steps=240,
                observation=observation,
                allowed_actions=THOR_BOOK_ACTIONS,
                retrieved_memory=(),
                shared_search=directive,
            )
            audit = audit_planner_request(request)
            self.assertTrue(audit.passed, audit.violations)
            decision = ThorBookReacquirePlanner().plan(request)
            self.assertEqual(decision.action, action)
            self.assertEqual(
                decision.reason_code,
                "shared_search_route_entry_recovery",
            )
            self.assertFalse(decision.memory_guided)
            state.record_result(directive, action=decision.action, success=True)
            ordinary = json.dumps(request.snapshot(include_digest=False))
            for forbidden in (
                "target_point",
                "anchor_id",
                "support_id",
                "candidate_order",
                "reachable_positions",
            ):
                self.assertNotIn(forbidden, ordinary)

        coverage = state.next_directive(_pose_observation(yaw=90.0))
        self.assertEqual(coverage["phase"], "coverage")
        self.assertEqual(coverage["action_index"], 0)
        self.assertEqual(state.entry_departure_action_count, 3)
        self.assertEqual(state.entry_recovery_action_count, 3)
        self.assertEqual(state.entry_recovery_pending_action_count, 0)
        self.assertEqual(
            SHARED_SEARCH_ENTRY_RECOVERY_POLICY_VERSION,
            "phase5-shared-search-entry-recovery-v1",
        )

    def test_entry_recovery_has_fixed_action_limit_and_ignores_nonpose_actions(self) -> None:
        route = load_frozen_search_route(ROUTE_ID)
        state = FrozenSearchRouteState(
            route,
            initial_observation=_pose_observation(yaw=90.0),
            entry_recovery_action_limit=2,
        )
        state.record_entry_departure_action(
            action={"action": "Pass"}, success=True
        )
        state.record_entry_departure_action(
            action={"action": "RotateLeft"}, success=True
        )
        state.record_entry_departure_action(
            action={"action": "MoveAhead"}, success=True
        )
        with self.assertRaisesRegex(SearchRouteError, "limit exceeded"):
            state.record_entry_departure_action(
                action={"action": "LookDown"}, success=True
            )
        self.assertEqual(state.entry_departure_action_count, 2)
        self.assertEqual(SHARED_SEARCH_ENTRY_RECOVERY_ACTION_LIMIT, 64)

    def test_three_stale_variants_share_route_actions_and_no_private_fields(self) -> None:
        route = load_frozen_search_route(ROUTE_ID)
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            summaries: dict[str, dict[str, Any]] = {}
            traces: dict[str, list[dict[str, Any]]] = {}
            for variant in ("no_memory", "short_memory_k2", "object_memory"):
                output_dir = root / variant
                summaries[variant] = ThorEpisodeRunner(
                    ThorEpisodeConfig(
                        task="thor_book_reacquire_k2",
                        scene="FloorPlan1",
                        planner="deterministic",
                        memory=variant,
                        search_route_id=ROUTE_ID,
                        condition="stale_r1",
                        mode="formal",
                        max_steps=20,
                        output_dir=output_dir,
                        save_frames=False,
                        trace_html=False,
                        visualize=False,
                    ),
                    env=_RelocatableBookThorEnv(),
                    intervention=_FrozenBookRelocation(),
                    search_route=route,
                ).run()
                traces[variant] = [
                    json.loads(line)
                    for line in (output_dir / "episode.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                ]
                ordinary_text = (output_dir / "episode.jsonl").read_text(
                    encoding="utf-8"
                )
                for forbidden in (
                    "destination_yaw",
                    "target_point",
                    "private_registry",
                    "anchor_id",
                ):
                    self.assertNotIn(forbidden, ordinary_text)

        for variant, summary in summaries.items():
            self.assertTrue(summary["success"], (variant, summary["failure_reason"]))
            self.assertTrue(summary["information_boundary_passed"])
            self.assertEqual(summary["shared_search_route_id"], ROUTE_ID)
            self.assertEqual(
                summary["shared_search_action_sequence_digest"], ROUTE_DIGEST
            )
            self.assertEqual(summary["shared_search_coverage_action_count"], 3)
            self.assertEqual(summary["search_rotation_count"], 3)
            self.assertEqual(summary["shared_search_route_entry_mismatch_count"], 0)
            self.assertEqual(summary["shared_search_route_exhausted_count"], 0)
            self.assertEqual(summary["shared_search_action_failure_count"], 0)

        self.assertEqual(
            summaries["no_memory"]["shared_search_alignment_action_count"], 1
        )
        self.assertEqual(
            summaries["short_memory_k2"]["shared_search_alignment_action_count"],
            1,
        )
        self.assertEqual(
            summaries["object_memory"]["shared_search_alignment_action_count"],
            0,
        )

        coverage_actions: dict[str, list[dict[str, Any]]] = {}
        for variant, trace in traces.items():
            coverage = [
                record
                for record in trace
                if isinstance(
                    record["planner_input"]["request"].get("shared_search"),
                    dict,
                )
                and record["planner_input"]["request"]["shared_search"].get(
                    "phase"
                ) == "coverage"
            ]
            self.assertEqual(
                [
                    record["planner_input"]["request"]["shared_search"][
                        "action_index"
                    ]
                    for record in coverage
                ],
                [0, 1, 2],
            )
            coverage_actions[variant] = [
                record["planner_decision"]["action"] for record in coverage
            ]
        self.assertEqual(
            coverage_actions["no_memory"], coverage_actions["short_memory_k2"]
        )
        self.assertEqual(
            coverage_actions["no_memory"], coverage_actions["object_memory"]
        )

    def test_route_action_failure_invalidates_episode(self) -> None:
        class _BlockedCoverageEnv(_RelocatableBookThorEnv):
            def step(self, action_dict: dict[str, Any]) -> Any:
                if (
                    action_dict.get("action") == "RotateRight"
                    and self.yaw == 90
                    and self.book_yaw == 0
                ):
                    self.last_event = self._event(
                        last_action="RotateRight",
                        success=False,
                        error="simulated frozen-route failure",
                    )
                    return self.last_event
                return super().step(action_dict)

        with tempfile.TemporaryDirectory() as temporary_dir:
            summary = ThorEpisodeRunner(
                ThorEpisodeConfig(
                    task="thor_book_reacquire_k2",
                    memory="no_memory",
                    search_route_id=ROUTE_ID,
                    condition="stale_r1",
                    max_steps=20,
                    output_dir=Path(temporary_dir) / "blocked",
                    trace_html=False,
                ),
                env=_BlockedCoverageEnv(),
                intervention=_FrozenBookRelocation(),
                search_route=load_frozen_search_route(ROUTE_ID),
            ).run()
        self.assertFalse(summary["success"])
        self.assertIn("shared_search_action_failed", summary["failure_reason"])
        self.assertEqual(summary["shared_search_action_failure_count"], 1)


if __name__ == "__main__":
    unittest.main()

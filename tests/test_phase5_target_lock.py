"""Offline acceptance tests for the shared Phase 5 target-lock policy."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from embodied_memory_thor.phase4.contracts import (
    EVALUATOR_CANARY,
    PlannerRequest,
    audit_planner_request,
)
from embodied_memory_thor.phase4.planners import (
    THOR_BOOK_ACTIONS,
    ThorBookReacquirePlanner,
    validate_planner_decision,
)
from embodied_memory_thor.phase4.runner import ThorEpisodeConfig, ThorEpisodeRunner
from embodied_memory_thor.phase5.target_lock import SharedTargetLockPolicy
from tests.test_phase4_single_case import _SingleCaseThorEnv


class _TransientLossThorEnv(_SingleCaseThorEnv):
    """Lose Book after approach; MoveBack restores the safe visible view."""

    def __init__(self) -> None:
        self.target_lock_pickup_attempts = 0
        super().__init__()

    def reset(self, scene: str) -> Any:
        self.target_lock_pickup_attempts = 0
        return super().reset(scene)

    def step(self, action_dict: dict[str, Any]) -> Any:
        action = str(action_dict.get("action", ""))
        if action == "MoveBack":
            self.z -= 0.25
            self.last_event = self._event(last_action=action, success=True)
            return self.last_event
        if action == "PickupObject" and self.target_lock_pickup_attempts == 0:
            self.target_lock_pickup_attempts += 1
            self.last_event = self._event(
                last_action=action,
                success=False,
                error="simulated initial pickup distance failure",
            )
            return self.last_event
        return super().step(action_dict)


def _observation(
    *, visible: bool, picked: bool = False, z: float = 0.0
) -> dict[str, Any]:
    objects = []
    if visible and not picked:
        objects.append(
            {
                "objectType": "Book",
                "objectId": "Book|visible-current-observation",
                "position": {"x": 0.0, "y": 0.8, "z": 2.0},
                "visible": True,
                "pickupable": True,
            }
        )
    return {
        "scene_name": "OfflineTargetLockFixture",
        "agent": {
            "position": {"x": 0.0, "y": 0.9, "z": z},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
            "cameraHorizon": 0.0,
            "isStanding": True,
        },
        "objects": objects,
        "inventory": (
            [{"objectId": "Book|visible-current-observation", "objectType": "Book"}]
            if picked
            else []
        ),
        "last_action": "Pass",
        "last_action_success": True,
        "last_action_error": "",
    }


def _request(observation: dict[str, Any], directive: dict[str, Any]) -> PlannerRequest:
    return PlannerRequest(
        task_name="thor_book_reacquire_k2",
        instruction="Reacquire and pick up the Book.",
        task_stage="pickup_book" if observation["objects"] else "reacquire_book",
        step=1,
        max_steps=40,
        observation=observation,
        allowed_actions=THOR_BOOK_ACTIONS,
        target_lock=directive,
    )


class Phase5TargetLockTests(unittest.TestCase):
    def test_visible_target_prioritizes_pickup_before_fallback(self) -> None:
        policy = SharedTargetLockPolicy(target_type="Book")
        observation = _observation(visible=True)
        directive = policy.next_directive(
            observation, allowed_actions=THOR_BOOK_ACTIONS
        )
        self.assertEqual(
            directive["action"],
            {"action": "PickupObject", "objectId": "Book|visible-current-observation"},
        )
        request = _request(observation, directive)
        audit = audit_planner_request(request)
        self.assertTrue(audit.passed, audit.violations)
        decision = ThorBookReacquirePlanner().plan(request)
        self.assertEqual(decision.action, directive["action"])
        self.assertEqual(decision.reason_code, "target_lock_pickup_attempt")
        self.assertTrue(validate_planner_decision(decision, request)[0])

    def test_pickup_distance_failure_then_approach_then_pickup_success(self) -> None:
        policy = SharedTargetLockPolicy(target_type="Book")
        visible = _observation(visible=True)
        pickup = policy.next_directive(visible, allowed_actions=THOR_BOOK_ACTIONS)
        policy.record_result(
            pickup,
            success=False,
            error_message="too far away",
            observation_after=visible,
            allowed_actions=THOR_BOOK_ACTIONS,
        )
        approach = policy.next_directive(visible, allowed_actions=THOR_BOOK_ACTIONS)
        self.assertEqual(approach["action"], {"action": "MoveAhead"})
        policy.record_result(
            approach,
            success=True,
            error_message="",
            observation_after=_observation(visible=True, z=0.25),
            allowed_actions=THOR_BOOK_ACTIONS,
        )
        retry = policy.next_directive(
            _observation(visible=True, z=0.25), allowed_actions=THOR_BOOK_ACTIONS
        )
        self.assertEqual(retry["action"]["action"], "PickupObject")
        policy.record_result(
            retry,
            success=True,
            error_message="",
            observation_after=_observation(visible=False, picked=True, z=0.25),
            allowed_actions=THOR_BOOK_ACTIONS,
        )
        metrics = policy.snapshot()
        self.assertEqual(metrics["target_lock_pickup_attempt_count"], 2)
        self.assertTrue(metrics["picked_after_target_lock"])

    def test_moveahead_loss_uses_moveback_then_reacquires_and_picks(self) -> None:
        policy = SharedTargetLockPolicy(target_type="Book")
        visible = _observation(visible=True)
        pickup = policy.next_directive(visible, allowed_actions=THOR_BOOK_ACTIONS)
        policy.record_result(
            pickup,
            success=False,
            error_message="too far",
            observation_after=visible,
            allowed_actions=THOR_BOOK_ACTIONS,
        )
        approach = policy.next_directive(visible, allowed_actions=THOR_BOOK_ACTIONS)
        policy.record_result(
            approach,
            success=True,
            error_message="",
            observation_after=_observation(visible=False, z=0.25),
            allowed_actions=THOR_BOOK_ACTIONS,
        )
        recovery = policy.next_directive(
            _observation(visible=False, z=0.25), allowed_actions=THOR_BOOK_ACTIONS
        )
        self.assertEqual(recovery["action"], {"action": "MoveBack"})
        policy.record_result(
            recovery,
            success=True,
            error_message="",
            observation_after=visible,
            allowed_actions=THOR_BOOK_ACTIONS,
        )
        retry = policy.next_directive(visible, allowed_actions=THOR_BOOK_ACTIONS)
        self.assertEqual(retry["action"]["action"], "PickupObject")
        policy.record_result(
            retry,
            success=True,
            error_message="",
            observation_after=_observation(visible=False, picked=True),
            allowed_actions=THOR_BOOK_ACTIONS,
        )
        metrics = policy.snapshot()
        self.assertEqual(metrics["transient_visibility_loss_count"], 1)
        self.assertEqual(metrics["local_recovery_action_count"], 1)
        self.assertEqual(metrics["target_reacquired_after_loss_count"], 1)
        self.assertTrue(metrics["picked_after_target_lock"])

    def test_recovery_budget_exhaustion_records_failure_without_private_data(self) -> None:
        policy = SharedTargetLockPolicy(
            target_type="Book", recovery_action_budget=3
        )
        visible = _observation(visible=True)
        pickup = policy.next_directive(visible, allowed_actions=THOR_BOOK_ACTIONS)
        policy.record_result(
            pickup,
            success=False,
            error_message="too far",
            observation_after=visible,
            allowed_actions=THOR_BOOK_ACTIONS,
        )
        approach = policy.next_directive(visible, allowed_actions=THOR_BOOK_ACTIONS)
        hidden = _observation(visible=False, z=0.25)
        policy.record_result(
            approach,
            success=True,
            error_message="",
            observation_after=hidden,
            allowed_actions=THOR_BOOK_ACTIONS,
        )
        for _ in range(3):
            recovery = policy.next_directive(hidden, allowed_actions=THOR_BOOK_ACTIONS)
            self.assertIsNotNone(recovery)
            policy.record_result(
                recovery,
                success=True,
                error_message="",
                observation_after=hidden,
                allowed_actions=THOR_BOOK_ACTIONS,
            )
        self.assertIsNone(
            policy.next_directive(hidden, allowed_actions=THOR_BOOK_ACTIONS)
        )
        snapshot = policy.snapshot()
        self.assertEqual(
            snapshot["target_lock_failed_reason"],
            "local_recovery_budget_exhausted",
        )
        serialized = json.dumps(snapshot)
        for forbidden in (
            EVALUATOR_CANARY,
            "target_point",
            "private_registry",
            "PlaceObjectAtPoint",
            "relocation_destination",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_non_distance_pickup_failure_does_not_trigger_blind_approach(self) -> None:
        policy = SharedTargetLockPolicy(target_type="Book")
        visible = _observation(visible=True)
        pickup = policy.next_directive(visible, allowed_actions=THOR_BOOK_ACTIONS)
        policy.record_result(
            pickup,
            success=False,
            error_message="inventory already contains another object",
            observation_after=visible,
            allowed_actions=THOR_BOOK_ACTIONS,
        )
        self.assertIsNone(
            policy.next_directive(visible, allowed_actions=THOR_BOOK_ACTIONS)
        )
        self.assertEqual(
            policy.snapshot()["target_lock_failed_reason"],
            "pickup_failure_not_distance_or_angle_related",
        )

    def test_never_visible_leaves_old_fallback_untouched(self) -> None:
        policy = SharedTargetLockPolicy(target_type="Book")
        hidden = _observation(visible=False)
        self.assertIsNone(
            policy.next_directive(hidden, allowed_actions=THOR_BOOK_ACTIONS)
        )
        self.assertEqual(policy.snapshot()["target_lock_entered_count"], 0)

    def test_all_memory_variants_receive_identical_target_lock_actions(self) -> None:
        actions = {}
        for variant in ("no_memory", "short_memory_k2", "object_memory"):
            policy = SharedTargetLockPolicy(target_type="Book")
            directive = policy.next_directive(
                _observation(visible=True), allowed_actions=THOR_BOOK_ACTIONS
            )
            actions[variant] = directive["action"]
        self.assertEqual(len({json.dumps(action, sort_keys=True) for action in actions.values()}), 1)

    def test_runner_uses_same_transient_loss_recovery_for_all_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            summaries = {}
            lock_actions = {}
            for variant in ("no_memory", "short_memory_k2", "object_memory"):
                output = root / variant
                summaries[variant] = ThorEpisodeRunner(
                    ThorEpisodeConfig(
                        task="thor_book_reacquire_k2",
                        memory=variant,
                        mode="formal",
                        max_steps=20,
                        output_dir=output,
                        save_frames=False,
                        trace_html=False,
                        visualize=False,
                    ),
                    env=_TransientLossThorEnv(),
                ).run()
                trace = [
                    json.loads(line)
                    for line in (output / "episode.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                ]
                lock_actions[variant] = [
                    row["planner_decision"]["action"]["action"]
                    for row in trace
                    if row["planner_decision"]["reason_code"].startswith(
                        "target_lock_"
                    )
                ]
                ordinary = json.dumps(trace)
                for forbidden in (
                    EVALUATOR_CANARY,
                    "target_point",
                    "private_registry",
                    "PlaceObjectAtPoint",
                    "relocation_destination",
                ):
                    self.assertNotIn(forbidden, ordinary)

        expected = ["PickupObject", "MoveAhead", "MoveBack", "PickupObject"]
        for variant, summary in summaries.items():
            self.assertTrue(summary["success"], variant)
            self.assertEqual(lock_actions[variant], expected)
            self.assertEqual(summary["transient_visibility_loss_count"], 1)
            self.assertEqual(summary["local_recovery_action_count"], 1)
            self.assertEqual(summary["target_reacquired_after_loss_count"], 1)
            self.assertTrue(summary["picked_after_target_lock"])
            self.assertTrue(summary["information_boundary_passed"])

    def test_old_floorplan202_failure_evidence_remains_readable(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (root / "docs" / "evidence" / "phase5_floorplan202_anchor_qualification.json")
            .read_text(encoding="utf-8")
        )
        self.assertFalse(evidence["result"]["passed"])
        self.assertEqual(evidence["result"]["candidate_trial_count"], 12)
        self.assertEqual(evidence["result"]["rediscovered_but_not_picked_count"], 4)

    def test_qualification_summary_aggregation_is_coordinate_free(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "scripts" / "qualify_phase5_anchors.py"
        spec = importlib.util.spec_from_file_location("qualifier_target_lock", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        summary = module._aggregate_target_lock_metrics(
            [
                {
                    "common_fallback_audit": {
                        "target_visible_event_count": 2,
                        "target_lock_entered_count": 1,
                        "target_lock_pickup_attempt_count": 2,
                        "transient_visibility_loss_count": 1,
                        "local_recovery_action_count": 1,
                        "target_reacquired_after_loss_count": 1,
                        "picked_after_target_lock": True,
                        "target_lock_failed_reason": "",
                    }
                }
            ]
        )
        self.assertTrue(summary["picked_after_target_lock"])
        self.assertNotIn("objectId", json.dumps(summary))
        self.assertNotIn("position", json.dumps(summary))


if __name__ == "__main__":
    unittest.main()

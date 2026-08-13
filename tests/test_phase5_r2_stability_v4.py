"""Offline acceptance for R2 three-reset stability and qualifier v4."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from embodied_memory_thor.phase5.anchors import stable_digest
from embodied_memory_thor.phase5.r2_stability import (
    STABILITY_POLICY_VERSION,
    StabilityQueryError,
    audit_start_pose_stability,
)


POSES = [
    {"x": float(index), "y": 0.9, "z": 0.0, "rotation": 0.0,
     "horizon": 0.0, "standing": True}
    for index in range(3)
]


class _StabilityEnv:
    def __init__(self, pass_counts: Mapping[str, int], *, query_failure_at: int | None = None) -> None:
        self.pass_counts = dict(pass_counts)
        self.query_failure_at = query_failure_at
        self.reset_count = 0
        self.query_count = 0
        self.trial_by_pose: dict[str, int] = {}
        self.metadata: dict[str, Any] = {}
        self.actions: list[tuple[int, Mapping[str, Any]]] = []

    def reset(self, scene: str) -> Any:
        self.reset_count += 1
        self.metadata = {"sceneName": scene}
        return SimpleNamespace(metadata=self.metadata)

    def get_evaluator_state(self) -> Mapping[str, Any]:
        return self.metadata

    def step(self, action: Mapping[str, Any]) -> Any:
        self.actions.append((self.reset_count, deepcopy(dict(action))))
        if action["action"] == "GetInteractablePoses":
            self.query_count += 1
            if self.query_failure_at == self.query_count:
                return SimpleNamespace(metadata={
                    "lastActionSuccess": False,
                    "errorMessage": "fixture query failure",
                })
            return SimpleNamespace(metadata={
                "lastActionSuccess": True,
                "errorMessage": "",
                "actionReturn": deepcopy(POSES),
            })
        pose_key = str(int(float(action["x"])))
        trial = self.trial_by_pose.get(pose_key, 0) + 1
        self.trial_by_pose[pose_key] = trial
        passed = trial <= self.pass_counts[pose_key]
        return SimpleNamespace(metadata={
            "lastActionSuccess": True,
            "objects": [
                {"objectId": "Cup|private", "visible": passed, "pickupable": True},
                {"objectId": "CoffeeMachine|private", "visible": False, "isToggled": False},
            ],
        })


class Phase5R2StabilityV4Tests(unittest.TestCase):
    @staticmethod
    def _script(name: str) -> Any:
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(name, root / "scripts" / name)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_stability_classifies_three_two_and_zero_of_three(self) -> None:
        env = _StabilityEnv({"0": 3, "1": 2, "2": 0})
        stable, audit = audit_start_pose_stability(
            env,
            scene="FloorPlanFixture",
            cup_id="Cup|private",
            machine_id="CoffeeMachine|private",
            poses=POSES,
        )
        self.assertEqual(stable, [POSES[0]])
        self.assertEqual(
            [row["classification"] for row in audit],
            ["stable", "visibility_unstable", "ineligible"],
        )
        self.assertEqual([row["successful_trial_count"] for row in audit], [3, 2, 0])
        resets = [reset for reset, action in env.actions if action["action"] == "GetInteractablePoses"]
        self.assertEqual(len(resets), 9)
        self.assertEqual(len(set(resets)), 9)

    def test_query_failure_is_explicit_and_never_silently_skipped(self) -> None:
        with self.assertRaisesRegex(StabilityQueryError, "repeated pose query failed"):
            audit_start_pose_stability(
                _StabilityEnv({"0": 3, "1": 3, "2": 3}, query_failure_at=2),
                scene="FloorPlanFixture",
                cup_id="Cup|private",
                machine_id="CoffeeMachine|private",
                poses=POSES,
            )

    def test_public_stability_summary_has_no_private_pose_or_identity(self) -> None:
        module = self._script("audit_phase5_r2_start_stability.py")
        summary = module.build_public_summary(
            scene="FloorPlanFixture",
            poses=POSES,
            audit=[{
                "pose_order": 1,
                "pose_digest": "a" * 64,
                "classification": "stable",
                "stable": True,
                "trials": [{"passed": True}] * 3,
            }],
            cup_audit=[{"cup_order": 1, "selected": True}],
            restoration={"passed": True},
            git_state={"code_revision": "b" * 40, "working_tree_dirty": False, "head_pushed": True},
            output_dir=Path("outputs/private"),
        )
        serialized = json.dumps(summary, sort_keys=True)
        self.assertEqual(summary["classification"], "start_visibility_stability_passed")
        self.assertEqual(summary["stable_pose_count"], 1)
        for forbidden in ("Cup|", "CoffeeMachine|", "TeleportFull", '"x"', '"y"', '"z"'):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(summary["routes_built_or_executed"])
        self.assertFalse(summary["planner_run"])
        self.assertFalse(summary["memory_agents_run"])

    def test_v4_pairing_is_rank_balanced_and_outcome_independent(self) -> None:
        module = self._script("qualify_phase5_r2_v4.py")
        pairs = module._candidate_pairs(POSES, list(reversed(POSES)))
        self.assertEqual(len(pairs), 9)
        self.assertEqual([(row[0], row[1]) for row in pairs[:5]], [
            (1, 1), (1, 2), (2, 1), (2, 2), (1, 3),
        ])
        self.assertNotIn("trial", module._candidate_pairs.__code__.co_varnames)
        self.assertNotIn("outcome", module._candidate_pairs.__code__.co_varnames)

    def test_v4_registered_classification_and_public_summary_are_safe(self) -> None:
        module = self._script("qualify_phase5_r2_v4.py")
        self.assertEqual(
            module.classify_candidate_batch([{
                "first_trial": {"reason": "target_not_rediscovered_before_fallback_exhaustion"}
            }]),
            "target_reacquisition_not_achieved_by_registered_visual_fallback",
        )
        summary = module.build_public_summary(
            scene="FloorPlanFixture",
            git_state={"code_revision": "b" * 40, "working_tree_dirty": False, "head_pushed": True},
            output_dir=Path("outputs/private"),
            cup_audit=[{"cup_order": 1, "selected": True}],
            stability_audit=[{"stable": False, "classification": "visibility_unstable"}],
            candidate_plan={"candidate_pairs": [], "candidate_plan_digest": "a" * 64},
            trials=[],
            selected_public=None,
            selected_private=None,
            classification="scene_start_visibility_unstable_no_stable_pose",
            failure_reason="fixture",
            restoration={"passed": True},
        )
        self.assertTrue(summary["scene_skip_allowed"])
        self.assertFalse(summary["fallback_target_or_anchor_input_used"])
        serialized = json.dumps(summary, sort_keys=True)
        for forbidden in ("Cup|", "CoffeeMachine|", "TeleportFull", '"x"', '"y"', '"z"'):
            self.assertNotIn(forbidden, serialized)

    def test_v4_config_freezes_historical_runtime_routes_and_evidence(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "configs" / "phase5_r2_qualification_v4.json").read_text(encoding="utf-8"))
        self.assertEqual(config["start_stability_trials_per_pose"], 3)
        self.assertEqual(config["fallback_action_limit"], 2048)
        self.assertTrue(config["candidate_freeze_before_task_outcomes"])
        self.assertFalse(config["memory_agents_run"])
        for relative, expected in config["historical_artifacts_frozen"].items():
            actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)


if __name__ == "__main__":
    unittest.main()

"""Offline acceptance for the paired FloorPlan5 horizon diagnostic."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


class Phase5R2FloorPlan5HorizonDiagnosticTests(unittest.TestCase):
    @staticmethod
    def _module():
        root = Path(__file__).resolve().parents[1]
        path = root / "scripts" / "diagnose_phase5_r2_floorplan5_horizon.py"
        spec = importlib.util.spec_from_file_location("diagnose_r2_floorplan5_horizon", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_treatment_removes_only_frozen_horizon_boundary(self) -> None:
        module = self._module()
        control = {
            "actions": [
                {"action": {"action": "LookUp"}, "phase": "coverage_absolute_horizon_alignment"},
                {"action": {"action": "RotateRight"}, "phase": "coverage_scan"},
                {"action": {"action": "MoveAhead"}, "phase": "coverage_move"},
                {"action": {"action": "LookDown"}, "phase": "coverage_initial_horizon_restore"},
            ],
            "absolute_scan_horizon_degrees": 0.0,
        }
        treatment = module.build_downward_treatment_route(
            control, expected_control_count=4
        )
        self.assertEqual(
            [row["action"]["action"] for row in treatment["actions"]],
            ["RotateRight", "MoveAhead"],
        )
        self.assertEqual(treatment["absolute_scan_horizon_degrees"], 30.0)
        self.assertTrue(treatment["spatial_action_sequence_unchanged"])
        with self.assertRaisesRegex(ValueError, "frozen horizon boundary"):
            module.build_downward_treatment_route(
                {"actions": control["actions"][1:]}, expected_control_count=3
            )

    def test_public_summary_attributes_only_clean_control_fail_treatment_pass(self) -> None:
        module = self._module()

        def trial(passed: bool, reason: str, actions: int) -> dict:
            return {
                "passed": passed,
                "reason": reason,
                "preconditions": {"all": True},
                "subgoal_route_replay": {"passed": True},
                "toggle": {"success": True},
                "fallback": {
                    "action_log": [{"success": True} for _ in range(actions)],
                    "discovery_step": 10 if passed else None,
                    "target_lock_entered_count": 1 if passed else 0,
                    "target_lock_pickup_attempt_count": 1 if passed else 0,
                },
            }

        summary = module.build_public_summary(
            arms=[
                ("control_0_degrees", trial(False, "target_not_rediscovered_before_fallback_exhaustion", 162)),
                ("treatment_downward_30_degrees", trial(True, "", 20)),
            ],
            git_state={"code_revision": "a" * 40, "working_tree_dirty": False},
            output_dir=Path("outputs/private"),
        )
        self.assertTrue(summary["integrity_passed"])
        self.assertTrue(summary["vertical_scan_coverage_attributed"])
        self.assertFalse(summary["memory_agents_run"])
        serialized = json.dumps(summary, sort_keys=True)
        for forbidden in ("Cup|", "CoffeeMachine|", "TeleportFull", '"x"', '"y"', '"z"'):
            self.assertNotIn(forbidden, serialized)

    def test_config_freezes_one_pair_and_private_source_digests(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = json.loads((
            root / "configs" / "phase5_r2_floorplan5_paired_horizon_diagnostic_v1.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(config["candidate_order"], 2)
        self.assertEqual(config["paired_order"], [
            "control_0_degrees", "treatment_downward_30_degrees"
        ])
        self.assertEqual(config["control_fallback_action_count"], 162)
        self.assertEqual(config["treatment_fallback_action_count"], 160)
        self.assertTrue(config["same_start_subgoal_toggle_and_spatial_fallback"])
        self.assertFalse(config["memory_agents_run"])
        self.assertFalse(config["formal_use_allowed"])


if __name__ == "__main__":
    unittest.main()

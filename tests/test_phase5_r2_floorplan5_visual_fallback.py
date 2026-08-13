"""Offline gates for the FloorPlan5 exhaustive visual fallback diagnostic."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import unittest
from pathlib import Path


class Phase5R2FloorPlan5VisualFallbackTests(unittest.TestCase):
    @staticmethod
    def _module():
        root = Path(__file__).resolve().parents[1]
        path = root / "scripts" / "diagnose_phase5_r2_floorplan5_visual_fallback.py"
        spec = importlib.util.spec_from_file_location(
            "diagnose_r2_floorplan5_visual_fallback", path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_precommit_freezes_privacy_parity_memory_and_prior_evidence(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = json.loads((
            root / "configs" / "phase5_r2_floorplan5_visual_fallback_diagnostic_v1.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(config["scene"], "FloorPlan5")
        self.assertEqual(config["candidate_order"], 2)
        self.assertEqual(
            config["frozen_failure_classification"], "visual_coverage_failure"
        )
        construction = config["route_construction"]
        self.assertEqual(construction["fallback_action_limit"], 2048)
        self.assertTrue(construction["route_built_once_and_shared_by_all_variants"])
        for key in (
            "target_or_anchor_input_used",
            "qualification_goal_input_used",
            "memory_variant_input_used",
        ):
            self.assertFalse(construction[key])
        self.assertEqual(config["shared_variant_contract"], [
            "no_memory", "short_memory_k2", "object_memory"
        ])
        for group in ("memory_provider_files_frozen", "prior_evidence_files_frozen"):
            for relative, expected in config[group].items():
                actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, relative)
        scope = config["real_run_scope"]
        self.assertTrue(scope["exactly_one_candidate"])
        self.assertFalse(scope["memory_agents_run"])
        self.assertFalse(scope["images_saved"])
        self.assertFalse(scope["formal_use_allowed"])

    def test_diagnostic_public_summary_is_coordinate_and_id_free(self) -> None:
        module = self._module()
        trial = {
            "passed": True,
            "reason": "",
            "preconditions": {"a": True},
            "subgoal_route_replay": {"passed": True},
            "toggle": {"success": True},
            "fallback": {
                "action_log": [{"success": True}],
                "discovery_step": 1,
                "pickup_step": 2,
                "coverage_actions_consumed": 1,
            },
        }
        route = {
            "route_version": "phase5-target-independent-exhaustive-visual-v1",
            "action_limit": 2048,
            "reachable_node_count": 127,
            "visited_node_count": 127,
            "scan_node_count": 127,
            "scan_horizons_degrees": [0.0, 30.0],
            "route_digest": "a" * 64,
            "target_or_anchor_input_used": False,
            "qualification_goal_input_used": False,
            "memory_variant_input_used": False,
            "every_reachable_node_visited": True,
            "every_reachable_node_scanned_at_both_horizons": True,
            "actions": [{"action": {"action": "RotateRight"}}],
        }
        summary = module.build_public_summary(
            trial=trial,
            restoration={"passed": True},
            route=route,
            git_state={"code_revision": "b" * 40, "working_tree_dirty": False},
            output_dir=Path("outputs/private"),
        )
        self.assertTrue(summary["diagnostic_passed"])
        self.assertTrue(summary["qualification_retry_allowed"])
        self.assertFalse(summary["memory_agents_run"])
        serialized = json.dumps(summary, sort_keys=True)
        for forbidden in ("Cup|", "CoffeeMachine|", "objectId", '"x":', '"y":', '"z":'):
            self.assertNotIn(forbidden, serialized)

    def test_diagnostic_runs_no_variants_and_uses_explicit_limit(self) -> None:
        module = self._module()
        source = inspect.getsource(module.main)
        self.assertNotIn("ThorEpisodeRunner", source)
        self.assertNotIn("no_memory", source)
        self.assertNotIn("short_memory_k2", source)
        self.assertNotIn("object_memory", source)
        self.assertIn("max_fallback_actions=VISUAL_FALLBACK_ACTION_LIMIT", source)

    def test_frozen_candidate_and_clean_failure_source_validate_offline(self) -> None:
        root = Path(__file__).resolve().parents[1]
        module = self._module()
        config = json.loads((
            root / "configs" / "phase5_r2_floorplan5_visual_fallback_diagnostic_v1.json"
        ).read_text(encoding="utf-8"))
        plan = json.loads((root / config["source_candidate_plan"]).read_text(encoding="utf-8"))
        qualification = json.loads((
            root / config["source_qualification"]
        ).read_text(encoding="utf-8"))
        candidate = module.validate_preconditions(config, plan, qualification)
        self.assertEqual(candidate["candidate_order"], 2)


if __name__ == "__main__":
    unittest.main()

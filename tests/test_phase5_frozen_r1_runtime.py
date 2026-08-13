"""Offline acceptance for the production frozen-R1 setup/intervention loader."""

from __future__ import annotations

import json
import tempfile
import unittest
import importlib.util
from unittest.mock import patch
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from embodied_memory_thor.phase4.runner import ThorEpisodeConfig, ThorEpisodeRunner
from embodied_memory_thor.phase5.anchors import stable_digest
from embodied_memory_thor.phase5.frozen_r1 import (
    FrozenR1ConfigurationError,
    load_frozen_r1_runtime,
)
from tests.test_phase5_stale_intervention import _RelocatableBookThorEnv


class _NativeFrozenR1Fixture(_RelocatableBookThorEnv):
    """Expose the two evaluator actions used by the production runtime."""

    def reset(self, scene: str) -> Any:
        if scene != "FloorPlanFixture":
            raise ValueError("fixture scene mismatch")
        return super().reset("FloorPlan1")

    def step(self, action_dict: Mapping[str, Any]) -> Any:
        action = str(action_dict.get("action", ""))
        if action == "TeleportFull":
            self.yaw = int(float(action_dict["rotation"])) % 360
            self.z = float(action_dict["z"])
            self.last_event = self._event(last_action=action, success=True)
            return self.last_event
        if action == "PlaceObjectAtPoint":
            self.book_yaw = 0
            self.last_event = self._event(last_action=action, success=True)
            return self.last_event
        return super().step(action_dict)


class Phase5FrozenR1RuntimeTests(unittest.TestCase):
    def test_production_probe_is_precommitted_excluded_and_private_safe(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (root / "configs" / "phase5_r1_production_integration_probe_v2.json")
            .read_text(encoding="utf-8")
        )
        spec = importlib.util.spec_from_file_location(
            "run_phase5_r1_production_probe",
            root / "scripts" / "run_phase5_r1_production_probe.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.validate_probe_config(config)
        self.assertFalse(config["included_in_formal_aggregate"])
        self.assertEqual(config["variants"], list(("no_memory", "short_memory_k2", "object_memory")))
        serialized = json.dumps(config, sort_keys=True)
        for forbidden in ("objectId", "support_id", "target_point", '"x"', '"y"', '"z"'):
            self.assertNotIn(forbidden, serialized)

    def test_cli_exposes_stale_condition_and_opaque_configuration(self) -> None:
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "run_thor_episode", root / "scripts" / "run_thor_episode.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        args = module.build_parser().parse_args(
            [
                "--task",
                "thor_book_reacquire_k2",
                "--configuration-id",
                "FloorPlan202_R1_fixed_start_001",
                "--condition",
                "stale_r1",
                "--planner",
                "no_memory",
                "--max-steps",
                "260",
            ]
        )
        config = module._build_config(args)
        self.assertEqual(config.condition, "stale_r1")
        self.assertEqual(config.max_steps, 260)

    def test_loader_binds_private_material_and_three_variants_do_not_leak_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            public_path, private_path, routes_path = self._write_fixture(root)
            runtime = load_frozen_r1_runtime(
                "Fixture_R1_fixed_start_001",
                public_set_path=public_path,
                private_set_path=private_path,
                search_routes_path=routes_path,
            )
            public_reference = runtime.configuration.public_reference()
            self.assertEqual(public_reference["configuration_id"], "Fixture_R1_fixed_start_001")
            public_text = json.dumps(public_reference, sort_keys=True)
            for forbidden in ("TeleportFull", "PlaceObjectAtPoint", '"x"', '"y"', '"z"'):
                self.assertNotIn(forbidden, public_text)

            actions: dict[str, list[str]] = {}
            for variant in ("no_memory", "short_memory_k2", "object_memory"):
                episode_dir = root / variant
                with patch(
                    "embodied_memory_thor.phase4.runner._git_state",
                    return_value={
                        "code_revision": "b" * 40,
                        "working_tree_dirty": False,
                    },
                ):
                    summary = ThorEpisodeRunner(
                        ThorEpisodeConfig(
                            task="thor_book_reacquire_k2",
                            scene="FloorPlanFixture",
                            planner="deterministic",
                            memory=variant,
                            search_route_id=runtime.search_route.route_id,
                            condition="stale_r1",
                            mode="formal",
                            max_steps=12,
                            output_dir=episode_dir,
                            save_frames=False,
                            trace_html=False,
                            visualize=False,
                            included_in_formal_aggregate=False,
                            run_purpose="phase5_r1_production_integration_probe",
                        ),
                        env=_NativeFrozenR1Fixture(),
                        search_route=runtime.search_route,
                        evaluator_setup=runtime.configuration,
                        intervention=runtime.intervention(),
                    ).run()
                self.assertTrue(summary["success"], (variant, summary["failure_reason"]))
                self.assertTrue(summary["information_boundary_passed"])
                self.assertEqual(summary["intervention_count"], 1)
                self.assertFalse(summary["included_in_formal_aggregate"])
                self.assertEqual(summary["evidence_status"], "excluded_engineering_probe")
                ordinary = (
                    (episode_dir / "setup.jsonl").read_text(encoding="utf-8")
                    + (episode_dir / "episode.jsonl").read_text(encoding="utf-8")
                )
                for forbidden in (
                    "TeleportFull",
                    "PlaceObjectAtPoint",
                    "Fixture_R1_stale_Book_anchor_001",
                    '"x": 9.0',
                    '"y": 8.0',
                    '"z": 7.0',
                ):
                    self.assertNotIn(forbidden, ordinary)
                self.assertIn("TeleportFull", (episode_dir / "evaluator_setup.jsonl").read_text(encoding="utf-8"))
                self.assertIn("PlaceObjectAtPoint", (episode_dir / "intervention.jsonl").read_text(encoding="utf-8"))
                records = [
                    json.loads(line)
                    for line in (episode_dir / "episode.jsonl").read_text(encoding="utf-8").splitlines()
                ]
                actions[variant] = [
                    row["planner_decision"]["action"]["action"]
                    for row in records
                    if isinstance(row["planner_input"]["request"].get("shared_search"), dict)
                    and row["planner_input"]["request"]["shared_search"].get("phase") == "coverage"
                ]
            self.assertEqual(actions["no_memory"], actions["short_memory_k2"])
            self.assertEqual(actions["no_memory"], actions["object_memory"])

    def test_loader_rejects_tampered_private_anchor_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            public_path, private_path, routes_path = self._write_fixture(root)
            private = json.loads(private_path.read_text(encoding="utf-8"))
            private["anchors"][0]["target_point"]["x"] = 999.0
            private_path.write_text(json.dumps(private), encoding="utf-8")
            with self.assertRaisesRegex(
                FrozenR1ConfigurationError, "anchor-set digest mismatch"
            ):
                load_frozen_r1_runtime(
                    "Fixture_R1_fixed_start_001",
                    public_set_path=public_path,
                    private_set_path=private_path,
                    search_routes_path=routes_path,
                )

    @staticmethod
    def _write_fixture(root: Path) -> tuple[Path, Path, Path]:
        start_pose = {
            "x": -1.0,
            "y": 0.9,
            "z": 1.25,
            "rotation": 90.0,
            "horizon": 0.0,
            "standing": True,
        }
        route_actions = [{"action": "RotateRight"}] * 3
        source_digest = "a" * 64
        route_id = "Fixture_R1_fixed_start_001_coverage"
        routes = {
            "schema_version": "phase5-search-route-v1",
            "routes": [
                {
                    "schema_version": "phase5-search-route-v1",
                    "route_id": route_id,
                    "task": "thor_book_reacquire_k2",
                    "scene": "FloorPlanFixture",
                    "source_qualification_route_digest": source_digest,
                    "action_sequence_digest": stable_digest(route_actions),
                    "action_codes": "RRR",
                    "target_or_anchor_input_used": False,
                }
            ],
        }
        private = {
            "anchor_set_version": "fixture-anchor-set-v1",
            "boundary": "EVALUATOR-ONLY FROZEN ANCHOR SET - NEVER PLANNER INPUT",
            "planner_visible": False,
            "included_in_planner_metrics": False,
            "anchor_count": 1,
            "scenes": ["FloorPlanFixture"],
            "sources": [],
            "anchors": [
                {
                    "anchor_id": "Fixture_R1_stale_Book_anchor_001",
                    "configuration_id": "Fixture_R1_fixed_start_001",
                    "scene": "FloorPlanFixture",
                    "target_object_id": "Book|1",
                    "target_object_type": "Book",
                    "target_point": {"x": 9.0, "y": 8.0, "z": 7.0},
                    "coverage_route_digest": source_digest,
                    "qualification_evidence": {
                        "first_physical_trial": {
                            "setup": [
                                {
                                    "action": {"action": "TeleportFull", **start_pose},
                                    "success": True,
                                }
                            ]
                        }
                    },
                }
            ],
        }
        private["private_anchor_set_digest"] = stable_digest(private)
        public = {
            "anchor_set_version": "fixture-anchor-set-v1",
            "private_anchor_set_digest": private["private_anchor_set_digest"],
            "target_anchor_count": 1,
            "scenes": [
                {
                    "scene": "FloorPlanFixture",
                    "configuration_id": "Fixture_R1_fixed_start_001",
                    "anchor_id": "Fixture_R1_stale_Book_anchor_001",
                    "start_pose_digest": stable_digest(start_pose),
                    "search_route_id": route_id,
                }
            ],
        }
        public_path = root / "public.json"
        private_path = root / "private.json"
        routes_path = root / "routes.json"
        public_path.write_text(json.dumps(public), encoding="utf-8")
        private_path.write_text(json.dumps(private), encoding="utf-8")
        routes_path.write_text(json.dumps(routes), encoding="utf-8")
        return public_path, private_path, routes_path


if __name__ == "__main__":
    unittest.main()

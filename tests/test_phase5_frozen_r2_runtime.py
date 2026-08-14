"""Offline acceptance for the production frozen-R2 runtime and probe."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

from embodied_memory_thor.phase4.runner import ThorEpisodeConfig, ThorEpisodeRunner
from embodied_memory_thor.phase5.anchors import stable_digest
from embodied_memory_thor.phase5.frozen_r2 import (
    PRIVATE_BOUNDARY,
    FrozenR2ConfigurationError,
    load_frozen_r2_runtime,
)
from embodied_memory_thor.phase5.search import load_frozen_search_route
from tests.test_phase5_ordered_task import _CupCoffeeThorEnv


class _NativeFrozenR2Fixture(_CupCoffeeThorEnv):
    def step(self, action_dict: Mapping[str, Any]) -> Any:
        if action_dict.get("action") == "TeleportFull":
            self.yaw = int(float(action_dict["rotation"])) % 360
            self.z = float(action_dict["z"])
            self.last_event = self._event(last_action="TeleportFull", success=True)
            return self.last_event
        return super().step(action_dict)


class Phase5FrozenR2RuntimeTests(unittest.TestCase):
    def test_floorplan4_qualified_routes_are_frozen_and_coordinate_free(self) -> None:
        root = Path(__file__).resolve().parents[1]
        subgoal = load_frozen_search_route(
            "FloorPlan4_R2_fixed_start_001_subgoal_v1"
        )
        fallback = load_frozen_search_route(
            "FloorPlan4_R2_fixed_start_001_fallback_absolute_v4"
        )
        self.assertEqual(subgoal.action_codes, "LFFFFFFRFFF")
        self.assertEqual(subgoal.action_count, 11)
        self.assertEqual(subgoal.route_role, "task_subgoal_navigation")
        self.assertTrue(subgoal.qualification_goal_input_used)
        self.assertEqual(fallback.action_count, 110)
        self.assertEqual(fallback.route_role, "target_independent_fallback")
        self.assertFalse(fallback.target_or_anchor_input_used)
        evidence = json.loads(
            (root / "docs" / "evidence" / "phase5_floorplan4_r2_v2_qualification.json")
            .read_text(encoding="utf-8")
        )
        self.assertTrue(evidence["passed"])
        self.assertFalse(evidence["memory_agents_run"])
        self.assertEqual(evidence["qualified_r2_count_after_scene"], 2)
        serialized = json.dumps(evidence, sort_keys=True)
        for forbidden in (
            "Cup|",
            "CoffeeMachine|",
            "TeleportFull",
            '"x"',
            '"y"',
            '"z"',
        ):
            self.assertNotIn(forbidden, serialized)

    def test_real_public_runtime_and_probe_are_coordinate_free(self) -> None:
        root = Path(__file__).resolve().parents[1]
        runtime = load_frozen_r2_runtime("FloorPlan3_R2_fixed_start_001")
        self.assertEqual(runtime.subgoal_route.action_codes, "FRFFFL")
        self.assertEqual(runtime.fallback_route.action_count, 110)
        public = runtime.configuration.public_reference()
        serialized = json.dumps(public, sort_keys=True)
        for forbidden in (
            "TeleportFull", "objectId", "target_cup", "coffee_machine_object",
            '"x"', '"y"', '"z"',
        ):
            self.assertNotIn(forbidden, serialized)

        probe = json.loads(
            (root / "configs" / "phase5_r2_production_integration_probe_v2.json")
            .read_text(encoding="utf-8")
        )
        module = self._probe_module(root)
        module.validate_probe_config(probe)
        self.assertFalse(probe["included_in_formal_aggregate"])
        self.assertEqual(
            probe["variants"], ["no_memory", "short_memory_k2", "object_memory"]
        )
        probe_text = json.dumps(probe, sort_keys=True)
        for forbidden in ("objectId", "TeleportFull", '"x"', '"y"', '"z"'):
            self.assertNotIn(forbidden, probe_text)

    def test_loader_binds_private_start_and_three_variants_share_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            public_path, private_path, routes_path = self._write_fixture(root)
            runtime = load_frozen_r2_runtime(
                "Fixture_R2_fixed_start_001",
                public_set_path=public_path,
                private_set_path=private_path,
                search_routes_path=routes_path,
            )
            summaries: dict[str, Mapping[str, Any]] = {}
            subgoal_actions: dict[str, list[str]] = {}
            for variant in ("no_memory", "short_memory_k2", "object_memory"):
                episode_dir = root / variant
                with patch(
                    "embodied_memory_thor.phase4.runner._git_state",
                    return_value={"code_revision": "b" * 40, "working_tree_dirty": False},
                ):
                    summary = ThorEpisodeRunner(
                        ThorEpisodeConfig(
                            task="thor_cup_after_coffee_subgoal",
                            scene="FloorPlan1",
                            planner="deterministic",
                            memory=variant,
                            subgoal_route_id=runtime.subgoal_route.route_id,
                            search_route_id=runtime.fallback_route.route_id,
                            condition="stable",
                            mode="formal",
                            max_steps=10,
                            output_dir=episode_dir,
                            save_frames=False,
                            trace_html=False,
                            visualize=False,
                            included_in_formal_aggregate=False,
                            run_purpose="phase5_r2_production_integration_probe",
                        ),
                        env=_NativeFrozenR2Fixture(),
                        subgoal_route=runtime.subgoal_route,
                        search_route=runtime.fallback_route,
                        evaluator_setup=runtime.configuration,
                    ).run()
                summaries[variant] = summary
                self.assertTrue(summary["success"], (variant, summary["failure_reason"]))
                self.assertTrue(summary["information_boundary_passed"])
                self.assertEqual(summary["evidence_status"], "excluded_engineering_probe")
                ordinary = (
                    (episode_dir / "setup.jsonl").read_text(encoding="utf-8")
                    + (episode_dir / "episode.jsonl").read_text(encoding="utf-8")
                )
                for forbidden in (
                    "TeleportFull", "candidate_order", "destination_pose",
                    "reachable_positions", "start_action", "target_cup_object_id",
                ):
                    self.assertNotIn(forbidden, ordinary)
                private_setup = (episode_dir / "evaluator_setup.jsonl").read_text(
                    encoding="utf-8"
                )
                self.assertIn("TeleportFull", private_setup)
                records = [
                    json.loads(line)
                    for line in (episode_dir / "episode.jsonl")
                    .read_text(encoding="utf-8").splitlines()
                ]
                subgoal_actions[variant] = [
                    row["planner_decision"]["action"]["action"]
                    for row in records
                    if isinstance(row["planner_input"]["request"].get("shared_search"), dict)
                    and row["planner_input"]["request"]["shared_search"].get("policy")
                    == "frozen_task_subgoal_route"
                ]
            self.assertEqual(subgoal_actions["no_memory"], subgoal_actions["short_memory_k2"])
            self.assertEqual(subgoal_actions["no_memory"], subgoal_actions["object_memory"])
            for summary in summaries.values():
                self.assertEqual(summary["shared_subgoal_action_sequence_digest"], runtime.subgoal_route.action_sequence_digest)
                self.assertEqual(summary["shared_search_action_sequence_digest"], runtime.fallback_route.action_sequence_digest)

    def test_loader_rejects_private_and_public_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            public_path, private_path, routes_path = self._write_fixture(root)
            private = json.loads(private_path.read_text(encoding="utf-8"))
            private["configurations"][0]["start_action"]["x"] = 99.0
            private_path.write_text(json.dumps(private), encoding="utf-8")
            with self.assertRaisesRegex(FrozenR2ConfigurationError, "runtime-set digest"):
                load_frozen_r2_runtime(
                    "Fixture_R2_fixed_start_001",
                    public_set_path=public_path,
                    private_set_path=private_path,
                    search_routes_path=routes_path,
                )

    def test_cli_accepts_opaque_ordered_r2_configuration(self) -> None:
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "run_thor_episode", root / "scripts" / "run_thor_episode.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        args = module.build_parser().parse_args([
            "--task", "thor_cup_after_coffee_subgoal",
            "--configuration-id", "FloorPlan3_R2_fixed_start_001",
            "--planner", "no_memory", "--max-steps", "140",
        ])
        self.assertEqual(args.configuration_id, "FloorPlan3_R2_fixed_start_001")
        self.assertIsNone(args.subgoal_route_id)

    @staticmethod
    def _probe_module(root: Path) -> Any:
        spec = importlib.util.spec_from_file_location(
            "run_phase5_r2_production_probe",
            root / "scripts" / "run_phase5_r2_production_probe.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _write_fixture(root: Path) -> tuple[Path, Path, Path]:
        start_pose = {
            "x": 7.0, "y": 0.9, "z": 1.0, "rotation": 0.0,
            "horizon": 0.0, "standing": True,
        }
        source_digest = "a" * 64

        def route(route_id: str, codes: str, role: str, goal_used: bool) -> dict[str, Any]:
            names = {"D": "LookDown", "F": "MoveAhead", "L": "RotateLeft", "R": "RotateRight", "U": "LookUp"}
            actions = [{"action": names[code]} for code in codes]
            digest = hashlib.sha256(json.dumps(
                actions, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            ).encode("utf-8")).hexdigest()
            return {
                "schema_version": "phase5-search-route-v1",
                "route_id": route_id,
                "task": "thor_cup_after_coffee_subgoal",
                "scene": "FloorPlan1",
                "source_qualification_route_digest": source_digest,
                "action_sequence_digest": digest,
                "action_codes": codes,
                "route_role": role,
                "qualification_goal_input_used": goal_used,
                "target_or_anchor_input_used": goal_used,
            }

        subgoal = route("Fixture_R2_subgoal", "R", "task_subgoal_navigation", True)
        fallback = route("Fixture_R2_fallback", "RRR", "target_independent_fallback", False)
        private = {
            "runtime_set_version": "phase5-r2-frozen-runtime-set-v1",
            "boundary": PRIVATE_BOUNDARY,
            "planner_visible": False,
            "included_in_planner_metrics": False,
            "configuration_count": 1,
            "configurations": [{
                "configuration_id": "Fixture_R2_fixed_start_001",
                "scene": "FloorPlan1",
                "target_cup_object_id": "Cup|1",
                "coffee_machine_object_id": "CoffeeMachine|1",
                "start_action": {"action": "TeleportFull", **start_pose},
                "start_pose_digest": stable_digest(start_pose),
                "source_qualification_digest": source_digest,
                "subgoal_route_id": subgoal["route_id"],
                "fallback_route_id": fallback["route_id"],
            }],
        }
        private["private_configuration_set_digest"] = stable_digest(private)
        public = {
            "runtime_set_version": "phase5-r2-frozen-runtime-set-v1",
            "private_configuration_set_digest": private["private_configuration_set_digest"],
            "configurations": [{
                "configuration_id": "Fixture_R2_fixed_start_001",
                "scene": "FloorPlan1",
                "start_pose_digest": stable_digest(start_pose),
                "source_qualification_digest": source_digest,
                "subgoal_route_id": subgoal["route_id"],
                "subgoal_route_action_sequence_digest": subgoal["action_sequence_digest"],
                "fallback_route_id": fallback["route_id"],
                "fallback_route_action_sequence_digest": fallback["action_sequence_digest"],
            }],
        }
        public_path = root / "public.json"
        private_path = root / "private.json"
        routes_path = root / "routes.json"
        public_path.write_text(json.dumps(public), encoding="utf-8")
        private_path.write_text(json.dumps(private), encoding="utf-8")
        routes_path.write_text(json.dumps({
            "schema_version": "phase5-search-route-v1", "routes": [subgoal, fallback],
        }), encoding="utf-8")
        return public_path, private_path, routes_path


if __name__ == "__main__":
    unittest.main()

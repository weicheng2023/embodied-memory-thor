"""Offline acceptance for the FloorPlan5 start-visibility census."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping


class Phase5R2StartVisibilityCensusTests(unittest.TestCase):
    @staticmethod
    def _module() -> Any:
        path = Path(__file__).resolve().parents[1] / "scripts" / "census_phase5_r2_start_visibility.py"
        spec = importlib.util.spec_from_file_location("census_phase5_r2_start_visibility", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_config_is_floorplan5_only_bounded_and_non_experimental(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = json.loads((
            root / "configs" / "phase5_r2_floorplan5_start_visibility_census_v1.json"
        ).read_text(encoding="utf-8"))
        self._module().validate_config(config)
        self.assertEqual(config["pose_scope"], "exhaustive selected-Cup standing pose list")
        self.assertFalse(config["formal_use_allowed"])
        forbidden = " ".join(config["forbidden_environment_actions"])
        for action in ("ToggleObjectOn", "PickupObject", "planner", "memory_variant"):
            self.assertIn(action, forbidden)

    def test_pose_audit_is_exhaustive_reset_isolated_and_boolean_only_for_decision(self) -> None:
        module = self._module()

        class _Env:
            def __init__(self) -> None:
                self.reset_count = 0
                self.steps: list[tuple[int, Mapping[str, Any]]] = []
                self.metadata: dict[str, Any] = {}

            def reset(self, scene: str) -> Any:
                self.reset_count += 1
                return SimpleNamespace(metadata={"sceneName": scene})

            def get_evaluator_state(self) -> Mapping[str, Any]:
                return self.metadata

            def step(self, action: Mapping[str, Any]) -> Any:
                self.steps.append((self.reset_count, dict(action)))
                eligible = action["x"] == 1.0
                metadata = {
                    "lastActionSuccess": True,
                    "objects": [
                        {"objectId": "Cup|private", "visible": True, "pickupable": True},
                        {"objectId": "CoffeeMachine|private", "visible": not eligible, "isToggled": False},
                    ],
                }
                return SimpleNamespace(metadata=metadata)

        poses = [
            {"x": 0.0, "y": 0.9, "z": 0.0, "rotation": 0.0, "horizon": 0.0, "standing": True},
            {"x": 1.0, "y": 0.9, "z": 0.0, "rotation": 0.0, "horizon": 0.0, "standing": True},
        ]
        env = _Env()
        rows = module.audit_start_poses(
            env, scene="FloorPlan5", cup_id="Cup|private",
            machine_id="CoffeeMachine|private", poses=poses,
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual([reset for reset, _ in env.steps], [1, 2])
        self.assertTrue(all(step["action"] == "TeleportFull" for _, step in env.steps))
        self.assertEqual([row["eligible"] for row in rows], [False, True])

    def test_public_summary_excludes_private_ids_poses_coordinates_and_actions(self) -> None:
        module = self._module()
        root = Path(__file__).resolve().parents[1]
        config = json.loads((
            root / "configs" / "phase5_r2_floorplan5_start_visibility_census_v1.json"
        ).read_text(encoding="utf-8"))
        row = {
            "pose_order": 7,
            "pose_digest": "a" * 64,
            "eligible": True,
            "preconditions": {field: True for field in config["required_preconditions"]},
        }
        summary = module.build_public_summary(
            config=config, rows=[row], cup_audit=[{"cup_order": 1, "selected": True}],
            git_state={"code_revision": "b" * 40, "working_tree_dirty": False},
            output_dir=Path("outputs/private"),
        )
        serialized = json.dumps(summary, sort_keys=True)
        self.assertEqual(summary["eligible_pose_count"], 1)
        self.assertEqual(summary["first_eligible_pose_order"], 7)
        for forbidden in ("Cup|", "CoffeeMachine|", "TeleportFull", '"pose"', '"x"', '"y"', '"z"'):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()

"""Offline tests for the bounded FloorPlan202 support-query isolation probe."""

from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "isolate_phase5_r1_support_mutation.py"
PROTOCOL_PATH = (
    ROOT / "configs" / "phase5_r1_support_mutation_isolation.json"
)


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "isolate_phase5_r1_support_mutation", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Event:
    def __init__(self, metadata: Mapping[str, Any]) -> None:
        self.metadata = dict(metadata)


class _IsolationEnv:
    def __init__(
        self,
        *,
        natural_jitter_per_pass: float = 0.0,
        material_query_type: str | None = None,
        failed_query_types: set[str] | None = None,
    ) -> None:
        self.natural_jitter_per_pass = natural_jitter_per_pass
        self.material_query_type = material_query_type
        self.failed_query_types = set(failed_query_types or set())
        self.actions_since_reset: list[str] = []
        self.reset_scenes: list[str] = []
        self._base_objects = [
            {
                "objectId": "Book|private",
                "objectType": "Book",
                "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "parentReceptacles": ["CoffeeTable|private"],
                "isMoving": False,
                "isPickedUp": False,
            },
            *[
                {
                    "objectId": f"{support_type}|private",
                    "objectType": support_type,
                    "receptacle": True,
                    "position": {"x": float(index + 1), "y": 1.0, "z": 0.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "parentReceptacles": None,
                    "isMoving": False,
                    "isPickedUp": False,
                }
                for index, support_type in enumerate(
                    ("CoffeeTable", "Shelf", "SideTable")
                )
            ],
        ]
        self._objects = deepcopy(self._base_objects)

    def reset(self, scene: str) -> _Event:
        self.reset_scenes.append(scene)
        self.actions_since_reset = []
        self._objects = deepcopy(self._base_objects)
        return _Event({"objects": deepcopy(self._objects)})

    def step(self, action: Mapping[str, Any]) -> _Event:
        action_name = str(action["action"])
        self.actions_since_reset.append(action_name)
        if action_name == "Pass":
            self._objects[0]["position"]["x"] += self.natural_jitter_per_pass
            success = True
            returned: list[dict[str, float]] | None = None
        else:
            support_type = str(action["objectId"]).split("|", 1)[0]
            if support_type == self.material_query_type:
                self._objects[0]["position"]["x"] += 0.01
            success = support_type not in self.failed_query_types
            returned = [{"x": 9.0, "y": 9.0, "z": 9.0}] if success else None
        return _Event(
            {
                "objects": deepcopy(self._objects),
                "lastActionSuccess": success,
                "actionReturn": returned,
            }
        )

    def get_evaluator_state(self) -> dict[str, Any]:
        return {"objects": deepcopy(self._objects)}


class Phase5SupportMutationIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()
        cls.protocol = cls.module.load_protocol(PROTOCOL_PATH)

    def test_protocol_is_floorplan202_only_and_bounded(self) -> None:
        self.assertEqual(self.protocol["scene"], "FloorPlan202")
        self.assertEqual(
            self.protocol["isolated_query_support_types"],
            ["CoffeeTable", "Shelf", "SideTable"],
        )
        self.assertEqual(
            self.protocol["allowed_actions"],
            ["GetSpawnCoordinatesAboveReceptacle", "Pass"],
        )
        self.assertFalse(self.protocol["constraints"]["other_scenes_allowed"])
        self.assertFalse(self.protocol["constraints"]["placement_allowed"])

    def test_case_a_requires_query_specific_material_change(self) -> None:
        env = _IsolationEnv(material_query_type="CoffeeTable")
        result = self.module.run_isolation(env, self.protocol)
        self.assertEqual(result["classification"], "case_a_query_changes_scene")
        self.assertEqual(result["material_query_support_types"], ["CoffeeTable"])
        self.assertFalse(result["baseline"]["comparison"]["material_change"])
        self.assertTrue(result["all_trials_reset_isolated"])
        self.assertEqual(set(env.reset_scenes), {"FloorPlan202"})

    def test_case_b_detects_subthreshold_natural_jitter(self) -> None:
        env = _IsolationEnv(natural_jitter_per_pass=0.00001)
        result = self.module.run_isolation(env, self.protocol)
        self.assertEqual(
            result["classification"],
            "case_b_natural_settling_or_digest_sensitivity",
        )
        baseline = result["baseline"]["comparison"]
        self.assertTrue(baseline["strict_digest_changed"])
        self.assertTrue(baseline["strict_only_or_subthreshold_change"])
        self.assertFalse(baseline["material_change"])

    def test_rotation_wraparound_is_a_small_circular_delta(self) -> None:
        before = {
            "Book|private": {
                "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                "rotation": {"x": 0.0, "y": 359.99, "z": 0.0},
                "parentReceptacles": None,
                "isMoving": False,
            }
        }
        after = deepcopy(before)
        after["Book|private"]["rotation"]["y"] = 0.01
        comparison = self.module.compare_snapshots(
            before,
            after,
            position_threshold=0.001,
            rotation_threshold=0.1,
        )
        self.assertAlmostEqual(
            comparison["max_rotation_component_delta_degrees"], 0.02, places=6
        )
        self.assertTrue(comparison["strict_digest_changed"])
        self.assertFalse(comparison["material_change"])

    def test_failed_query_is_still_isolated_and_assessed(self) -> None:
        env = _IsolationEnv(failed_query_types={"Shelf", "SideTable"})
        result = self.module.run_isolation(env, self.protocol)
        self.assertEqual(
            result["failed_query_support_types"], ["Shelf", "SideTable"]
        )
        self.assertEqual(result["classification"], "no_state_change_detected")
        for trial in result["query_trials"]:
            self.assertEqual(trial["query_attempt_count"], 1)
            self.assertTrue(trial["reset_after_trial"])

    def test_public_summary_excludes_identifiers_coordinates_and_actions(self) -> None:
        result = self.module.run_isolation(_IsolationEnv(), self.protocol)
        summary = self.module.build_public_summary(
            protocol=self.protocol,
            result=result,
            git_state={"code_revision": "a" * 40, "working_tree_dirty": False},
            raw_digest="b" * 64,
        )
        serialized = json.dumps(summary, sort_keys=True)
        for forbidden in (
            "objectId",
            '"position"',
            '"rotation"',
            '"x"',
            '"y"',
            '"z"',
            "target_point",
            "private_registry",
            "PlaceObjectAtPoint",
            "PickupObject",
            "forceAction",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(summary["other_scenes_started"])
        self.assertFalse(summary["placement_actions_run"])
        self.assertFalse(summary["memory_agents_run"])
        self.assertFalse(summary["images_saved"])

    def test_real_public_evidence_records_case_b_without_private_fields(self) -> None:
        evidence = json.loads(
            (
                ROOT
                / "docs"
                / "evidence"
                / "phase5_r1_support_mutation_isolation.json"
            ).read_text(encoding="utf-8")
        )
        self.module.audit_public_summary(evidence)
        self.assertTrue(evidence["case_b_supported"])
        self.assertFalse(evidence["case_a_supported"])
        self.assertFalse(
            evidence["review"]["query_specific_material_change_detected"]
        )
        self.assertFalse(evidence["other_scenes_started"])
        self.assertFalse(evidence["placement_actions_run"])


if __name__ == "__main__":
    unittest.main()

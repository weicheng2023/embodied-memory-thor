"""Offline tests for the matched-action FloorPlan302 mutation isolation."""

from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "isolate_phase5_floorplan302_support_mutation.py"
PROTOCOL_PATH = (
    ROOT / "configs" / "phase5_floorplan302_support_mutation_isolation.json"
)
EVIDENCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "phase5_floorplan302_support_mutation_isolation.json"
)


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "isolate_phase5_floorplan302_support_mutation", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Event:
    def __init__(self, metadata: Mapping[str, Any]) -> None:
        self.metadata = dict(metadata)


class _FloorPlan302Env:
    def __init__(
        self,
        *,
        control_rotation_delta: float = 0.0,
        query_rotation_delta: float = 0.0,
        failed_types: set[str] | None = None,
    ) -> None:
        self.control_rotation_delta = control_rotation_delta
        self.query_rotation_delta = query_rotation_delta
        self.failed_types = set(failed_types or set())
        self.reset_scenes: list[str] = []
        self.followup_actions_per_reset: list[int] = []
        self.query_actions: list[dict[str, Any]] = []
        self._pass_count = 0
        self._followup_count = 0
        counts = {"Bed": 1, "Desk": 1, "Shelf": 5, "SideTable": 2}
        self._base_objects = [
            {
                "objectId": "Book|private",
                "objectType": "Book",
                "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "parentReceptacles": ["Desk|private|1"],
                "isMoving": False,
                "isPickedUp": False,
            }
        ]
        for support_type, count in counts.items():
            for ordinal in range(1, count + 1):
                self._base_objects.append(
                    {
                        "objectId": f"{support_type}|private|{ordinal}",
                        "objectType": support_type,
                        "receptacle": True,
                        "position": {
                            "x": float(len(self._base_objects)),
                            "y": 1.0,
                            "z": 0.0,
                        },
                        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "parentReceptacles": None,
                        "isMoving": False,
                        "isPickedUp": False,
                    }
                )
        self._objects = deepcopy(self._base_objects)

    def reset(self, scene: str) -> _Event:
        if self.reset_scenes:
            self.followup_actions_per_reset.append(self._followup_count)
        self.reset_scenes.append(scene)
        self._objects = deepcopy(self._base_objects)
        self._pass_count = 0
        self._followup_count = 0
        return _Event({"objects": deepcopy(self._objects)})

    def step(self, action: Mapping[str, Any]) -> _Event:
        action_name = str(action["action"])
        if action_name == "Pass":
            self._pass_count += 1
            if self._pass_count > 5:
                self._followup_count += 1
                self._objects[0]["rotation"]["y"] += self.control_rotation_delta
            return _Event(
                {
                    "objects": deepcopy(self._objects),
                    "lastActionSuccess": True,
                    "actionReturn": None,
                }
            )
        self._followup_count += 1
        self.query_actions.append(dict(action))
        self._objects[0]["rotation"]["y"] += self.query_rotation_delta
        support_type = str(action["objectId"]).split("|", 1)[0]
        success = support_type not in self.failed_types
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


class Phase5FloorPlan302MutationIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()
        cls.protocol = cls.module.load_protocol(PROTOCOL_PATH)

    def test_protocol_freezes_matched_action_scope_and_alignment(self) -> None:
        self.assertEqual(self.protocol["scene"], "FloorPlan302")
        self.assertEqual(self.protocol["control_replicate_count"], 3)
        self.assertEqual(self.protocol["control_followup_pass_count"], 1)
        self.assertEqual(
            self.protocol["expected_receptacle_counts"],
            {"Bed": 1, "Desk": 1, "Shelf": 5, "SideTable": 2},
        )
        self.assertTrue(self.protocol["spawn_query_anywhere"])
        self.assertTrue(self.protocol["query_parameter_alignment_with_qualifier"])
        self.assertFalse(self.protocol["constraints"]["other_scenes_allowed"])
        self.assertFalse(self.protocol["constraints"]["placement_allowed"])

    def test_all_nine_queries_are_reset_isolated_and_anywhere_true(self) -> None:
        env = _FloorPlan302Env()
        result = self.module.run_isolation(env, self.protocol)
        env.reset("FloorPlan302")
        self.assertEqual(len(result["query_trials"]), 9)
        self.assertEqual(len(env.query_actions), 9)
        self.assertTrue(all(action["anywhere"] is True for action in env.query_actions))
        self.assertTrue(result["all_trials_reset_isolated"])
        self.assertTrue(result["all_trials_one_followup_action"])
        self.assertTrue(all(count <= 1 for count in env.followup_actions_per_reset))
        self.assertEqual(set(env.reset_scenes), {"FloorPlan302"})

    def test_case_a_requires_stable_controls_and_material_queries(self) -> None:
        result = self.module.run_isolation(
            _FloorPlan302Env(control_rotation_delta=0.0, query_rotation_delta=0.2),
            self.protocol,
        )
        self.assertEqual(
            result["classification"], "case_a_query_specific_material_change"
        )
        self.assertEqual(result["material_query_trial_count"], 9)

    def test_case_b_requires_queries_within_material_control_envelope(self) -> None:
        result = self.module.run_isolation(
            _FloorPlan302Env(control_rotation_delta=0.3, query_rotation_delta=0.2),
            self.protocol,
        )
        self.assertEqual(
            result["classification"],
            "case_b_queries_within_natural_control_envelope",
        )
        self.assertEqual(result["query_exceeding_control_envelope_count"], 0)

    def test_mixed_result_stays_inconclusive(self) -> None:
        result = self.module.run_isolation(
            _FloorPlan302Env(control_rotation_delta=0.2, query_rotation_delta=0.4),
            self.protocol,
        )
        self.assertEqual(
            result["classification"], "mixed_material_variation_inconclusive"
        )
        self.assertEqual(result["query_exceeding_control_envelope_count"], 9)

    def test_failed_queries_are_measured_not_hidden(self) -> None:
        result = self.module.run_isolation(
            _FloorPlan302Env(failed_types={"Shelf", "SideTable"}), self.protocol
        )
        self.assertEqual(result["failed_query_trial_count"], 7)
        self.assertEqual(len(result["query_trials"]), 9)

    def test_public_summary_excludes_private_state_and_coordinates(self) -> None:
        result = self.module.run_isolation(_FloorPlan302Env(), self.protocol)
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
        self.assertTrue(summary["spawn_query_anywhere"])
        self.assertFalse(summary["other_scenes_started"])
        self.assertFalse(summary["placement_actions_run"])
        self.assertFalse(summary["memory_agents_run"])

    def test_real_result_is_mixed_and_blocks_census_v3(self) -> None:
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        self.module.audit_public_summary(evidence)
        review = evidence["post_run_review"]
        self.assertEqual(
            evidence["classification"], "mixed_material_variation_inconclusive"
        )
        self.assertEqual(evidence["control_envelope"]["material_control_count"], 3)
        self.assertEqual(evidence["material_query_trial_count"], 9)
        self.assertEqual(evidence["query_exceeding_control_envelope_count"], 1)
        self.assertEqual(evidence["failed_query_trial_count"], 0)
        self.assertFalse(review["case_a_supported"])
        self.assertFalse(review["case_b_supported"])
        self.assertFalse(review["census_v3_run_allowed"])
        self.assertTrue(review["stop_required"])
        self.assertTrue(evidence["spawn_query_anywhere"])
        self.assertTrue(evidence["query_parameter_alignment_with_qualifier"])
        self.assertFalse(evidence["other_scenes_started"])
        self.assertFalse(evidence["placement_actions_run"])
        self.assertFalse(evidence["pickup_actions_run"])
        self.assertFalse(evidence["fallback_route_run"])
        self.assertFalse(evidence["memory_agents_run"])
        self.assertFalse(evidence["images_saved"])


if __name__ == "__main__":
    unittest.main()

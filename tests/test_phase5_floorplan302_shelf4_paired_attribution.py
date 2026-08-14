"""Offline tests for the stronger Shelf-4 paired attribution design."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embodied_memory_thor.phase5.paired_attribution import (  # noqa: E402
    classify_paired_attribution,
    paired_mean_interval,
)


SCRIPT_PATH = (
    ROOT / "scripts" / "probe_phase5_floorplan302_shelf4_paired_attribution.py"
)
PROTOCOL_PATH = (
    ROOT / "configs" / "phase5_floorplan302_shelf4_paired_attribution.json"
)
EVIDENCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "phase5_floorplan302_shelf4_paired_attribution.json"
)


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "probe_phase5_floorplan302_shelf4_paired_attribution", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Event:
    def __init__(self, metadata: Mapping[str, Any]) -> None:
        self.metadata = dict(metadata)


class _PairedEnv:
    def __init__(
        self,
        *,
        control_rotation_deltas: Sequence[float],
        query_rotation_deltas: Sequence[float],
        fail_query_index: int | None = None,
    ) -> None:
        self.control_rotation_deltas = list(control_rotation_deltas)
        self.query_rotation_deltas = list(query_rotation_deltas)
        self.fail_query_index = fail_query_index
        self.control_index = 0
        self.query_index = 0
        self.reset_scenes: list[str] = []
        self.followups_per_reset: list[int] = []
        self.query_actions: list[dict[str, Any]] = []
        self._pass_count = 0
        self._followups = 0
        self._base_objects = [
            {
                "objectId": "Book|private",
                "objectType": "Book",
                "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "parentReceptacles": ["Shelf|private|4"],
                "isMoving": False,
                "isPickedUp": False,
            },
            *[
                {
                    "objectId": f"Shelf|private|{ordinal}",
                    "objectType": "Shelf",
                    "receptacle": True,
                    "position": {"x": float(ordinal), "y": 1.0, "z": 0.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "parentReceptacles": None,
                    "isMoving": False,
                    "isPickedUp": False,
                }
                for ordinal in range(1, 6)
            ],
        ]
        self._objects = deepcopy(self._base_objects)

    def reset(self, scene: str) -> _Event:
        if self.reset_scenes:
            self.followups_per_reset.append(self._followups)
        self.reset_scenes.append(scene)
        self._pass_count = 0
        self._followups = 0
        self._objects = deepcopy(self._base_objects)
        return _Event({"objects": deepcopy(self._objects)})

    def step(self, action: Mapping[str, Any]) -> _Event:
        action_name = str(action["action"])
        if action_name == "Pass":
            self._pass_count += 1
            if self._pass_count > 5:
                self._followups += 1
                delta = self.control_rotation_deltas[self.control_index]
                self.control_index += 1
                self._objects[0]["rotation"]["y"] += delta
            success = True
            returned = None
        else:
            self._followups += 1
            self.query_actions.append(dict(action))
            delta = self.query_rotation_deltas[self.query_index]
            self._objects[0]["rotation"]["y"] += delta
            success = self.query_index != self.fail_query_index
            self.query_index += 1
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


class Phase5FloorPlan302Shelf4PairedAttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()
        cls.protocol = cls.module.load_protocol(PROTOCOL_PATH)

    def _run(
        self,
        *,
        controls: Sequence[float],
        queries: Sequence[float],
        fail_query_index: int | None = None,
    ) -> tuple[_PairedEnv, dict[str, Any]]:
        env = _PairedEnv(
            control_rotation_deltas=controls,
            query_rotation_deltas=queries,
            fail_query_index=fail_query_index,
        )
        return env, self.module.run_probe(env, self.protocol)

    def test_protocol_freezes_balanced_twelve_pair_design(self) -> None:
        self.assertEqual(self.protocol["scene"], "FloorPlan302")
        self.assertEqual(self.protocol["target_support_type"], "Shelf")
        self.assertEqual(self.protocol["target_support_ordinal"], 4)
        self.assertEqual(self.protocol["pair_count"], 12)
        self.assertEqual(
            self.protocol["pair_orders"].count("query_then_pass"), 6
        )
        self.assertEqual(
            self.protocol["pair_orders"].count("pass_then_query"), 6
        )
        self.assertEqual(
            self.protocol["statistics"]["per_endpoint_one_sided_alpha"], 0.025
        )
        self.assertFalse(self.protocol["constraints"]["census_v3_allowed"])

    def test_paired_interval_uses_query_minus_control(self) -> None:
        interval = paired_mean_interval([2.0, 4.0], [1.0, 2.0], t_critical=2.0)
        self.assertEqual(interval["pair_count"], 2)
        self.assertAlmostEqual(interval["mean_paired_difference"], 1.5)
        self.assertAlmostEqual(interval["median_paired_difference"], 1.5)
        self.assertEqual(interval["minimum_paired_difference"], 1.0)
        self.assertEqual(interval["maximum_paired_difference"], 2.0)
        self.assertEqual(interval["positive_difference_count"], 2)
        self.assertAlmostEqual(
            interval["sample_standard_deviation_of_differences"],
            2 ** -0.5,
        )

    def test_all_trials_are_reset_isolated_balanced_and_anywhere_true(self) -> None:
        env, result = self._run(controls=[0.2] * 12, queries=[0.2] * 12)
        env.reset("FloorPlan302")
        self.assertEqual(len(result["trials"]), 24)
        self.assertEqual(len(result["pairs"]), 12)
        self.assertEqual(len(env.query_actions), 12)
        self.assertTrue(all(action["anywhere"] is True for action in env.query_actions))
        self.assertTrue(
            all(action["objectId"].endswith("|4") for action in env.query_actions)
        )
        self.assertTrue(all(count <= 1 for count in env.followups_per_reset))
        self.assertTrue(result["balanced_order"])
        self.assertEqual(set(env.reset_scenes), {"FloorPlan302"})
        for pair_number, order in enumerate(self.protocol["pair_orders"], start=1):
            observed = [
                row["condition"]
                for row in result["trials"]
                if row["pair"] == pair_number
            ]
            expected = (
                ["query", "pass"]
                if order == "query_then_pass"
                else ["pass", "query"]
            )
            self.assertEqual(observed, expected)

    def test_corrected_bounds_support_below_margin_effect(self) -> None:
        _, result = self._run(controls=[0.3] * 12, queries=[0.35] * 12)
        self.assertEqual(
            result["classification"], "no_material_query_effect_supported"
        )
        self.assertEqual(
            result["below_margin_endpoints"],
            [
                "max_position_delta_meters",
                "max_rotation_component_delta_degrees",
            ],
        )

    def test_corrected_bounds_support_query_effect_above_margin(self) -> None:
        _, result = self._run(controls=[0.2] * 12, queries=[0.4] * 12)
        self.assertEqual(
            result["classification"], "query_specific_material_effect_supported"
        )
        self.assertEqual(
            result["effect_endpoints"],
            ["max_rotation_component_delta_degrees"],
        )

    def test_uncertain_corrected_interval_remains_inconclusive(self) -> None:
        interval = paired_mean_interval(
            [0.05, 0.30] * 6,
            [0.10] * 12,
            t_critical=self.protocol["statistics"]["t_critical"],
        )
        decision = classify_paired_attribution(
            endpoint_intervals={
                "rotation": interval,
                "position": paired_mean_interval(
                    [0.0] * 12, [0.0] * 12, t_critical=2.200985160082949
                ),
            },
            practical_margins={"rotation": 0.1, "position": 0.001},
            control_logical_change_count=0,
            control_identity_change_count=0,
            query_logical_change_count=0,
            query_identity_change_count=0,
            failed_query_count=0,
        )
        self.assertEqual(
            decision["classification"], "paired_attribution_inconclusive"
        )

    def test_bound_equal_to_margin_remains_inconclusive(self) -> None:
        decision = classify_paired_attribution(
            endpoint_intervals={
                "rotation": {"lower_bound": 0.1, "upper_bound": 0.1},
                "position": {"lower_bound": 0.001, "upper_bound": 0.001},
            },
            practical_margins={"rotation": 0.1, "position": 0.001},
            control_logical_change_count=0,
            control_identity_change_count=0,
            query_logical_change_count=0,
            query_identity_change_count=0,
            failed_query_count=0,
        )
        self.assertEqual(
            decision["classification"], "paired_attribution_inconclusive"
        )

    def test_failed_query_has_explicit_incomplete_classification(self) -> None:
        _, result = self._run(
            controls=[0.2] * 12,
            queries=[0.2] * 12,
            fail_query_index=4,
        )
        self.assertEqual(result["classification"], "incomplete_failed_query")
        self.assertEqual(result["failed_query_count"], 1)

    def test_public_summary_excludes_private_state_and_actions(self) -> None:
        _, result = self._run(controls=[0.2] * 12, queries=[0.2] * 12)
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
        self.assertFalse(summary["census_v3_run"])

    def test_real_paired_result_stays_inconclusive_and_blocks_census(self) -> None:
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        self.module.audit_public_summary(evidence)
        review = evidence["post_run_review"]
        rotation = evidence["endpoint_intervals"][
            "max_rotation_component_delta_degrees"
        ]
        position = evidence["endpoint_intervals"]["max_position_delta_meters"]

        self.assertEqual(evidence["classification"], "paired_attribution_inconclusive")
        self.assertEqual(evidence["pair_count"], 12)
        self.assertEqual(len(evidence["trials"]), 24)
        self.assertEqual(evidence["failed_query_count"], 0)
        self.assertEqual(evidence["effect_endpoints"], [])
        self.assertEqual(
            evidence["below_margin_endpoints"], ["max_position_delta_meters"]
        )
        self.assertAlmostEqual(rotation["median_paired_difference"], 0.0)
        self.assertEqual(rotation["positive_difference_count"], 5)
        self.assertGreater(rotation["upper_bound"], 0.1)
        self.assertLess(position["upper_bound"], 0.001)
        self.assertFalse(review["query_specific_material_effect_supported"])
        self.assertFalse(review["no_material_query_effect_fully_supported"])
        self.assertTrue(review["no_material_position_effect_supported"])
        self.assertFalse(review["census_v3_run_allowed"])
        self.assertTrue(review["stop_required"])
        self.assertFalse(evidence["census_v3_run"])
        self.assertFalse(evidence["other_scenes_started"])
        self.assertFalse(evidence["placement_actions_run"])
        self.assertFalse(evidence["pickup_actions_run"])
        self.assertFalse(evidence["fallback_route_run"])
        self.assertFalse(evidence["memory_agents_run"])
        self.assertFalse(evidence["images_saved"])


if __name__ == "__main__":
    unittest.main()

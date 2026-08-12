"""Offline tests for the fixed-N independent Shelf-4 replication cohort."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tests.test_phase5_floorplan302_shelf4_paired_attribution import (  # noqa: E402
    _PairedEnv,
)


SCRIPT_PATH = (
    ROOT
    / "scripts"
    / "probe_phase5_floorplan302_shelf4_independent_replication.py"
)
PROTOCOL_PATH = (
    ROOT
    / "configs"
    / "phase5_floorplan302_shelf4_independent_replication.json"
)
EVIDENCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "phase5_floorplan302_shelf4_independent_replication.json"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "probe_phase5_floorplan302_shelf4_independent_replication", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Phase5FloorPlan302Shelf4IndependentReplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()
        cls.protocol = cls.module.load_protocol(PROTOCOL_PATH)

    def _run(self, *, controls: list[float], queries: list[float]):
        env = _PairedEnv(
            control_rotation_deltas=controls,
            query_rotation_deltas=queries,
        )
        return env, self.module.paired.run_probe(env, self.protocol)

    def test_protocol_freezes_independent_fixed_n_cohort(self) -> None:
        self.assertEqual(self.protocol["pair_count"], 24)
        self.assertEqual(self.protocol["pair_orders"].count("query_then_pass"), 12)
        self.assertEqual(self.protocol["pair_orders"].count("pass_then_query"), 12)
        self.assertEqual(self.protocol["statistics"]["degrees_of_freedom"], 23)
        self.assertAlmostEqual(
            self.protocol["statistics"]["t_critical"], 2.068657610419041
        )
        prior = self.protocol["prior_cohort"]
        self.assertTrue(prior["used_for_sample_size_planning"])
        self.assertFalse(prior["used_for_decision"])
        self.assertFalse(prior["pooled_with_replication"])
        execution = self.protocol["execution_policy"]
        self.assertTrue(execution["fixed_pair_count"])
        self.assertFalse(execution["interim_analysis_allowed"])
        self.assertFalse(execution["interim_output_allowed"])
        self.assertFalse(execution["optional_sample_extension_allowed"])

    def test_sample_size_planning_numbers_recompute(self) -> None:
        prior = self.protocol["prior_cohort"]
        expected_half_width = (
            self.protocol["statistics"]["t_critical"]
            * prior["planning_rotation_sd_difference_degrees"]
            / math.sqrt(self.protocol["pair_count"])
        )
        self.assertAlmostEqual(
            expected_half_width,
            prior["anticipated_replication_half_width_degrees"],
        )
        self.assertAlmostEqual(
            prior["planning_rotation_mean_difference_degrees"]
            + expected_half_width,
            prior["anticipated_rotation_upper_bound_degrees"],
        )

    def test_replication_has_24_pairs_48_isolated_trials(self) -> None:
        env, result = self._run(controls=[0.2] * 24, queries=[0.2] * 24)
        env.reset("FloorPlan302")
        self.assertEqual(len(result["pairs"]), 24)
        self.assertEqual(len(result["trials"]), 48)
        self.assertEqual(len(env.query_actions), 24)
        self.assertTrue(all(action["anywhere"] is True for action in env.query_actions))
        self.assertTrue(
            all(action["objectId"].endswith("|4") for action in env.query_actions)
        )
        self.assertTrue(all(count <= 1 for count in env.followups_per_reset))
        self.assertTrue(result["balanced_order"])
        self.assertEqual(set(env.reset_scenes), {"FloorPlan302"})

    def test_replication_decision_ignores_prior_cohort_values(self) -> None:
        first_protocol = deepcopy(self.protocol)
        second_protocol = deepcopy(self.protocol)
        second_protocol["prior_cohort"][
            "planning_rotation_mean_difference_degrees"
        ] = 999.0
        second_protocol["prior_cohort"][
            "planning_rotation_sd_difference_degrees"
        ] = 999.0
        first = self.module.paired.run_probe(
            _PairedEnv(
                control_rotation_deltas=[0.2] * 24,
                query_rotation_deltas=[0.25] * 24,
            ),
            first_protocol,
        )
        second = self.module.paired.run_probe(
            _PairedEnv(
                control_rotation_deltas=[0.2] * 24,
                query_rotation_deltas=[0.25] * 24,
            ),
            second_protocol,
        )
        self.assertEqual(first["classification"], second["classification"])
        self.assertEqual(first["endpoint_intervals"], second["endpoint_intervals"])

    def test_supported_no_effect_only_unlocks_separate_review(self) -> None:
        _, result = self._run(controls=[0.3] * 24, queries=[0.35] * 24)
        self.assertEqual(
            result["classification"], "no_material_query_effect_supported"
        )
        summary = self.module.build_public_summary(
            protocol=self.protocol,
            result=result,
            git_state={"code_revision": "a" * 40, "working_tree_dirty": False},
            raw_digest="b" * 64,
        )
        self.assertTrue(summary["census_v3_review_eligible"])
        self.assertFalse(summary["census_v3_run"])
        self.assertEqual(summary["decision_data"], "replication_cohort_only")
        self.assertFalse(summary["prior_cohort_used_for_decision"])
        self.assertFalse(summary["prior_cohort_pooled_with_replication"])

    def test_failure_before_full_cohort_writes_no_output(self) -> None:
        fake_env = Mock()
        fake_env.close = Mock()
        write_mock = Mock()
        with (
            patch.object(self.module.paired, "_git_state", return_value={
                "code_revision": "a" * 40,
                "working_tree_dirty": False,
            }),
            patch.object(self.module.paired, "ThorEnv", return_value=fake_env),
            patch.object(
                self.module.paired,
                "run_probe",
                side_effect=RuntimeError("incomplete fixed-N cohort"),
            ),
            patch.object(self.module.paired, "_write_json", write_mock),
        ):
            with self.assertRaisesRegex(RuntimeError, "incomplete fixed-N cohort"):
                self.module.main(
                    [
                        "--protocol",
                        str(PROTOCOL_PATH),
                        "--private-output",
                        "private.json",
                        "--public-output",
                        "public.json",
                    ]
                )
        write_mock.assert_not_called()
        fake_env.close.assert_called_once()

    def test_public_summary_excludes_private_state_and_scope_expansion(self) -> None:
        _, result = self._run(controls=[0.2] * 24, queries=[0.2] * 24)
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
        self.assertTrue(summary["fixed_pair_count"])
        self.assertFalse(summary["interim_analysis_run"])
        self.assertFalse(summary["interim_output_written"])
        self.assertFalse(summary["optional_sample_extension_allowed"])
        self.assertFalse(summary["other_scenes_started"])
        self.assertFalse(summary["placement_actions_run"])
        self.assertFalse(summary["memory_agents_run"])
        self.assertFalse(summary["census_v3_run"])

    def test_real_replication_supports_no_effect_but_blocks_current_v3(self) -> None:
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        self.module.paired.audit_public_summary(evidence)
        review = evidence["post_run_review"]
        rotation = evidence["endpoint_intervals"][
            "max_rotation_component_delta_degrees"
        ]
        position = evidence["endpoint_intervals"]["max_position_delta_meters"]

        self.assertEqual(
            evidence["classification"], "no_material_query_effect_supported"
        )
        self.assertEqual(evidence["pair_count"], 24)
        self.assertEqual(len(evidence["trials"]), 48)
        self.assertEqual(evidence["failed_query_count"], 0)
        self.assertEqual(evidence["effect_endpoints"], [])
        self.assertEqual(
            evidence["below_margin_endpoints"],
            [
                "max_position_delta_meters",
                "max_rotation_component_delta_degrees",
            ],
        )
        self.assertLess(rotation["upper_bound"], 0.1)
        self.assertLess(position["upper_bound"], 0.001)
        self.assertEqual(rotation["positive_difference_count"], 1)
        self.assertFalse(evidence["prior_cohort_used_for_decision"])
        self.assertFalse(evidence["prior_cohort_pooled_with_replication"])
        self.assertFalse(evidence["interim_analysis_run"])
        self.assertFalse(evidence["interim_output_written"])
        self.assertTrue(evidence["census_v3_review_eligible"])
        self.assertFalse(review["census_v3_run_allowed"])
        self.assertTrue(review["independent_no_material_query_effect_supported"])
        self.assertFalse(review["query_specific_material_effect_supported"])
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
